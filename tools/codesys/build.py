# -*- coding: utf-8 -*-
"""Сборка приложения CODESYS и сообщения компилятора — скрипт CODESYS Scripting (IronPython 2.7).

Запуск — только через tools/codesys/cds.py (python tools/codesys/cds.py build [--tests]):
по умолчанию в том же процессе сначала выполняется import (исходники — источник истины).

Шаг build: очищает сообщения всех активных категорий, выполняет app.rebuild() (полная сборка:
после удаления объектов или библиотек простой build() может ответить «уже собрано»), собирает
сообщения system.get_message_objects по всем категориям в журнал job["log"] (build/build.log)
и JSON job["report"] (build/build.json): категория, важность, текст, объект и позиция, код
сообщения (prefix + number, например C0032). Ошибки (Error, FatalError) — шаг не пройден.
IDE русская: строка итога — «Компиляция завершена -- N ошибок, M предупреждений».
"""
from __future__ import absolute_import, print_function, unicode_literals

import re

import cds_common as C

MYPY = False
if MYPY:  # pragma: no cover
    from typing import Any, Dict, List, Optional  # noqa: F401

ERROR_SEVERITIES = ('FatalError', 'Error')
WARNING_SEVERITIES = ('Warning',)
# «Компиляция завершена -- 0 ошибок, 0 предупреждений» (русская IDE) / «Build complete -- 0 errors, 0 warnings»
_SUMMARY_RE = re.compile(
    r'(\d+)\s+(?:ошиб\w*|errors?)\s*,\s*(\d+)\s+(?:предупрежд\w*|warnings?)', re.IGNORECASE | re.UNICODE
)


def _safe(fn, default=None):
    # type: (Any, Any) -> Any
    try:
        return fn()
    except Exception:
        return default


def message_record(category, description, msg):
    # type: (str, Optional[str], Any) -> Dict[str, Any]
    severity = C._text(_safe(lambda: msg.severity, '?'))
    prefix = _safe(lambda: msg.prefix)
    number = _safe(lambda: msg.number)
    code = None
    if number is not None:
        code = '%s%04d' % (C._text(prefix or ''), int(number))
    obj = _safe(lambda: msg.object)
    return {
        'category': description or category,
        'category_guid': category,
        'severity': severity,
        'text': C._text(_safe(lambda: msg.text, '')),
        'object': C.object_path(obj) if obj is not None else None,
        'position': C._text(_safe(lambda: msg.position_text)) if _safe(lambda: msg.position_text) else None,
        'code': code,
    }


def collect_messages():
    # type: () -> List[Dict[str, Any]]
    system = C.api().system
    records = []  # type: List[Dict[str, Any]]
    for cat in system.get_message_categories(True):
        guid = C._text(cat)
        try:
            description = system.get_message_category_description(cat)
        except Exception:
            description = None
        for msg in system.get_message_objects(cat):
            records.append(message_record(guid, C._text(description) if description else None, msg))
    return records


def clear_messages():
    # type: () -> None
    system = C.api().system
    for cat in system.get_message_categories(True):
        try:
            system.clear_messages(cat)
        except Exception:
            pass


def summarize(records):
    # type: (List[Dict[str, Any]]) -> Dict[str, Any]
    errors = [r for r in records if r['severity'] in ERROR_SEVERITIES]
    warnings = [r for r in records if r['severity'] in WARNING_SEVERITIES]
    summary_line = None
    summary = None
    for rec in records:
        match = _SUMMARY_RE.search(rec['text'])
        if match and ('омпиляция' in rec['text'] or 'uild' in rec['text']):
            summary_line = rec['text']
            summary = (int(match.group(1)), int(match.group(2)))
    return {
        'errors': len(errors),
        'warnings': len(warnings),
        'summary_line': summary_line,
        'summary_errors': summary[0] if summary else None,
        'summary_warnings': summary[1] if summary else None,
    }


def format_record(rec):
    # type: (Dict[str, Any]) -> str
    where = ''
    if rec.get('object'):
        where = ' [%s%s]' % (rec['object'], (', ' + rec['position']) if rec.get('position') else '')
    code = (rec['code'] + ' ') if rec.get('code') else ''
    return '%-11s %s%s%s' % (rec['severity'], code, rec['text'], where)


def run(ctx, step):
    # type: (C.Context, Dict[str, Any]) -> Dict[str, Any]
    log = C.Log(step.get('log'))
    try:
        proj, _ = ctx.open_project(step['project'], create=False, reopen=bool(step.get('reopen')), log=log)
        app = C.application(proj)
        clear_messages()
        log.info('сборка (rebuild) приложения проекта %s' % step['project'])
        app.rebuild()
        records = collect_messages()
        for rec in records:
            line = format_record(rec)
            if rec['severity'] in ERROR_SEVERITIES:
                log.error(line)
            elif rec['severity'] in WARNING_SEVERITIES:
                log.warn(line)
            else:
                log.info(line)
        summary = summarize(records)
        if (
            summary['summary_errors'] is not None
            and summary['summary_errors'] != summary['errors']
        ):
            log.warn('итог компилятора (%s ошибок) не совпадает с числом сообщений об ошибках (%d)'
                     % (summary['summary_errors'], summary['errors']))
        errors = max(summary['errors'], summary['summary_errors'] or 0)
        log.info('итог: ошибок %d, предупреждений %d' % (errors, summary['warnings']))
        result = {
            'ok': errors == 0,
            'project': step['project'],
            'errors': errors,
            'warnings': summary['warnings'],
            'summary_line': summary['summary_line'],
            'messages': records,
        }
        if step.get('report'):
            C.write_json(step['report'], result)
        if errors:
            result['error'] = 'сборка: ошибок %d (см. %s)' % (errors, step.get('log') or 'журнал')
        return result
    except Exception as exc:
        log.error('%s' % exc)
        raise
    finally:
        log.close()


if __name__ == '__main__':
    C.run_main('build')
