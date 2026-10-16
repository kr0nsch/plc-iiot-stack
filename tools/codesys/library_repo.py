# -*- coding: utf-8 -*-
"""Репозиторий библиотек CODESYS: проверка зависимостей и удаление версий — скрипт CODESYS Scripting (IronPython 2.7).

Запуск — только через tools/codesys/cds.py (cds.py deps, cds.py library --uninstall).

Шаги:
- deps: для каждого описания библиотеки (config.json: libraries) — установлена ли подходящая
  версия (точная или новейшая '*'), какие версии этой библиотеки есть, файл в репозитории и
  каких её собственных зависимостей (рекурсивно) нет в репозиториях (missing_dependencies).
  С install_missing отсутствующие ставятся из install_from (reinstall — повторно, даже если
  установлены). Сборку из соседних репозиториев (build_from_repo) выполняет cds.py, не этот шаг.
- uninstall: удаление версий библиотеки (название и компания — точно, без учёта регистра) из
  репозитория librarymanager.uninstall_library; каталог компании CODESYS удаляет сам, когда в нём
  не остаётся версий (проверено на 3.5.17.30).
"""
from __future__ import absolute_import, print_function, unicode_literals

import cds_common as C
import import_sources as I

MYPY = False
if MYPY:  # pragma: no cover
    from typing import Any, Dict, List  # noqa: F401


def _file_of(rec):
    # type: (Dict[str, Any]) -> Any
    try:
        return C._text(C.api().librarymanager.get_file_path(rec['obj']))
    except Exception:
        return None


def _versions(records, spec):
    # type: (List[Dict[str, Any]], Dict[str, Any]) -> List[str]
    found = set(r['version'] for r in records if C.lib_matches_identity(r, spec))
    return sorted(found, key=lambda v: C.parse_version(v) or (0,))


def run_deps(step, log):
    # type: (Dict[str, Any], C.Log) -> Dict[str, Any]
    records = C.installed_libraries()
    reinstall = set(step.get('reinstall') or [])
    entries = []  # type: List[Dict[str, Any]]
    for spec in step.get('specs') or []:
        key = C._text(spec.get('key'))
        rec = C.pick_library(records, spec)
        entry = {'key': key, 'pin': I._pin(spec), 'installed_now': False}  # type: Dict[str, Any]
        want_file = step.get('install_missing') and spec.get('install_from') and (rec is None or key in reinstall)
        if want_file:
            rec = I.install_from_file(spec, step.get('repository'), log)
            entry['installed_now'] = True
            records = C.installed_libraries()
        entry['installed_versions'] = _versions(records, spec)
        entry['found'] = rec is not None
        if rec is not None:
            entry.update({'displayname': rec['displayname'], 'version': rec['version'], 'title': rec['title'],
                          'company': rec['company'], 'namespace': rec['namespace'], 'file': _file_of(rec),
                          'missing_dependencies': C.missing_dependencies(rec, records)})
            log.info('%s %s: %s (%s)' % (key, entry['pin'], rec['displayname'], entry['file']))
            for dep in entry['missing_dependencies']:
                log.warn('%s: в репозиториях нет зависимости %s' % (rec['displayname'], dep))
        else:
            have = ', '.join(entry['installed_versions']) or '-'
            log.info('%s %s: нет (установлены: %s)' % (key, entry['pin'], have))
        entries.append(entry)
    return {'ok': True, 'libraries': entries}


def run_uninstall(step, log):
    # type: (Dict[str, Any], C.Log) -> Dict[str, Any]
    lm = C.api().librarymanager
    repo = C.find_repository(step.get('repository'))
    title = C._text(step['title']).lower()
    company = C._text(step['company']).lower()
    versions = [C.parse_version(v) for v in step.get('versions') or []]
    removed = []  # type: List[str]
    for ml in list(lm.get_all_libraries(repo)):
        rec = C.lib_record(ml)
        if rec['title'].lower() != title or rec['company'].lower() != company:
            continue
        if versions and C.parse_version(rec['version']) not in versions:
            continue
        lm.uninstall_library(repo, ml)
        removed.append(rec['displayname'])
        log.info('удалена %s из репозитория %s' % (rec['displayname'], C._text(repo.name)))
    left = [C.lib_record(ml)['version'] for ml in lm.get_all_libraries(repo)
            if C._text(ml.title).lower() == title and C._text(ml.company).lower() == company]
    if not removed:
        which = (' версий %s' % ', '.join(step['versions'])) if step.get('versions') else ''
        log.warn('в репозитории %s нет %s (%s)%s' % (C._text(repo.name), step['title'], step['company'], which))
    return {'ok': True, 'removed': removed, 'left': left, 'repository': C._text(repo.name)}


def run(ctx, step):
    # type: (C.Context, Dict[str, Any]) -> Dict[str, Any]
    log = C.Log(step.get('log'))
    try:
        if step.get('action') == 'uninstall':
            result = run_uninstall(step, log)
        else:
            result = run_deps(step, log)
        result['log_warnings'] = list(log.warnings)
        if step.get('report'):
            C.write_json(step['report'], dict((k, v) for k, v in result.items()))
        return result
    except Exception as exc:
        log.error('%s' % exc)
        raise
    finally:
        log.close()


if __name__ == '__main__':
    C.run_main('deps')
