# -*- coding: utf-8 -*-
"""Сборка библиотеки CODESYS из src/ — скрипт CODESYS Scripting (IronPython 2.7).

Запуск — только через tools/codesys/cds.py (python tools/codesys/cds.py library [--install] [--compiled]).

Как библиотека создаётся скриптом в SP17 (проверено на 3.5.17.30 зондами, docs/ASSUMPTIONS.md, D23–D27):
- projects.create(путь) всегда создаёт проект .project: путь X.library молча становится X.project.
  Поэтому проект создаётся во временный файл .project (на диск он не пишется) и сохраняется
  proj.save_as(X.library). Так же устроен шаблон IDE «Пустая библиотека»
  (Templates/EmptyLibrary.template — это Empty.project с расширением .library): в обоих случаях в
  проекте только Project Settings и __VisualizationStyle, без устройства и приложения.
- Объекты — в пуле POU корня проекта (proj.create_pou/create_dut/create_gvl/create_interface/
  create_folder), Library Manager пула — proj.get_library_manager().
- Project Information — proj.get_project_info() (объект создаётся при первом вызове): company,
  title, version, author, description, released, default_namespace (сеттер работает, хотя в стабах
  его нет) и values['Placeholder'].
- Проверка — proj.check_all_pool_objects() («Проверить все объекты пула»): компилирует пул и пишет
  сообщения в те же категории, что сборка приложения («Компиляция завершена -- N ошибок, ...»),
  с объектом и позицией ошибки.
- proj.save_as_compiled_library(путь) пишет .compiled-library (в справке ошибочно .compiled_library).
- librarymanager.install_library(файл, репозиторий, True) ставит библиотеку с заменой той же
  версии (с False — «Библиотека уже существует»); разные версии лежат рядом.

Шаг library: раскладка src/ (без tests/, без объектов library.exclude и Persistent Variables) ->
новая библиотека job["library"] (build/<имя>.library) с Project Information из config.json
(library), ссылки на библиотеки library.libraries, проверка пула. Ошибки проверки — шаг не пройден
(библиотека сохраняется для разбора в IDE, но не компилируется и не устанавливается). По флагам —
job["compiled"] (.compiled-library) и установка в репозиторий job["repository"] с проверкой
find_library. Журнал — job["log"] (build/library.log), отчёт — job["report"] (build/library.json).
"""
from __future__ import absolute_import, print_function, unicode_literals

import os

import build as B
import cds_common as C
import import_sources as I
import stlayout as L

MYPY = False
if MYPY:  # pragma: no cover
    from typing import Any, Dict, List, Optional, Tuple  # noqa: F401


def scan_library_sources(repo_root, exclude, tests_folder, log):
    # type: (str, List[str], str, C.Log) -> List[Tuple[L.StObject, List[str]]]
    """Объекты src/ для библиотеки: без library.exclude и без Persistent Variables."""
    skip = set(name.lower() for name in exclude)
    scanned = I.scan_sources(repo_root, False, tests_folder, log)
    for name in sorted(skip - set(obj.name.lower() for obj, _ in scanned)):
        log.warn('library.exclude: объекта %s нет в src/' % name)
    wanted = []  # type: List[Tuple[L.StObject, List[str]]]
    for obj, folder in scanned:
        if obj.name.lower() in skip:
            log.info('%s: исключён из библиотеки (config.json: library.exclude)' % obj.name)
            continue
        if obj.kind == L.KIND_PVL:
            log.warn('%s: Persistent Variables в библиотеку не входят (в SP17 скриптом не создаются)' % obj.main_path())
            continue
        wanted.append((obj, folder))
    if not wanted:
        raise C.StepError('в src/ нет объектов для библиотеки')
    return wanted


def _remove(path, log):
    # type: (str, C.Log) -> None
    if path and os.path.exists(path):
        os.remove(path)
        log.info('удалён %s' % path)


def set_project_info(proj, info, log):
    # type: (Any, Dict[str, Any], C.Log) -> Dict[str, Any]
    """Project Information библиотеки; возвращает то, что прочитано обратно из проекта."""
    pi = proj.get_project_info()
    pi.company = C._text(info['company'])
    pi.title = C._text(info['title'])
    pi.version = C._text(info['version'])
    pi.default_namespace = C._text(info['default_namespace'])
    if info.get('author'):
        pi.author = C._text(info['author'])
    if info.get('description'):
        pi.description = C._text(info['description'])
    pi.released = bool(info.get('released'))
    if info.get('placeholder'):
        pi.values['Placeholder'] = C._text(info['placeholder'])
    actual = {
        'company': C._text(pi.company),
        'title': C._text(pi.title),
        'version': C._text(pi.version),
        'default_namespace': C._text(pi.default_namespace),
        'released': bool(pi.released),
        'placeholder': info.get('placeholder') or None,
    }
    log.info('Project Information: %s' % ', '.join('%s=%s' % (k, actual[k]) for k in sorted(actual)))
    if C.parse_version(actual['version']) != C.parse_version(info['version']) or actual['title'] != info['title']:
        raise C.StepError('Project Information не применилась: %r' % (actual,))
    return actual


def placeholder_needs_consumer(resolution_info, redirected):
    # type: (Any, Any) -> bool
    """Плейсхолдер библиотеки разрешён не профилем библиотек, а её собственной настройкой?

    В пуле библиотеки свой плейсхолдер разрешается библиотекой по умолчанию
    (resolution_info 'Resolved by placeholder default library'; у Standard — 'Разрешено профилем
    библиотеки', resolver_guid у обоих одинаковый — проверено на 3.5.17.30) или перенаправлением.
    Потребителю ни то, ни другое не передаётся.
    """
    info = C._text(resolution_info or '').lower()
    return bool(redirected) or 'default' in info or 'по умолчанию' in info


def warn_unresolved_placeholders(libman, log):
    # type: (Any, C.Log) -> None
    """Предупреждение о плейсхолдерах библиотеки, которые профиль библиотек не разрешает.

    У потребителя такой библиотеки сборка падает («Библиотека X не добавлена в Менеджер
    библиотек»), пока он сам не добавит плейсхолдер с тем же именем; с ним — собирается
    (проверено на 3.5.17.30).
    """
    for ref in libman.references:
        rec = C.ref_record(ref)
        if rec['placeholder'] and placeholder_needs_consumer(C._attr(ref, 'resolution_info'),
                                                             C._attr(ref, 'is_redirected')):
            log.warn('плейсхолдер #%s (%s) профиль библиотек не разрешает: потребителям библиотеки нужна своя '
                     'ссылка-плейсхолдер #%s (libraries.<ключ>.placeholder), иначе их сборка не найдёт библиотеку; '
                     'обычная ссылка (без placeholder) такого требования не создаёт'
                     % (rec['placeholder'], rec['target'], rec['placeholder']))


def check_pool(proj, log):
    # type: (Any, C.Log) -> Dict[str, Any]
    """«Проверить все объекты пула»: сообщения компилятора, как у шага build."""
    B.clear_messages()
    proj.check_all_pool_objects()
    records = B.collect_messages()
    for rec in records:
        line = B.format_record(rec)
        if rec['severity'] in B.ERROR_SEVERITIES:
            log.error(line)
        elif rec['severity'] in B.WARNING_SEVERITIES:
            log.warn(line)
        else:
            log.info(line)
    summary = B.summarize(records)
    errors = max(summary['errors'], summary['summary_errors'] or 0)
    if summary['summary_line'] is None:
        log.warn('нет строки итога компилятора: проверка пула могла не выполниться')
    return {'errors': errors, 'warnings': summary['warnings'], 'summary_line': summary['summary_line'],
            'messages': records}


def install(path, repository, info, compiled, log):
    # type: (str, Optional[str], Dict[str, Any], bool, C.Log) -> Dict[str, Any]
    """Установка файла библиотеки в репозиторий с заменой той же версии; проверка find_library."""
    if not os.path.isfile(path):
        raise C.StepError('нет файла библиотеки для установки: %s' % path, C.EXIT_INTERNAL)
    lm = C.api().librarymanager
    repo = C.find_repository(repository)
    spec = {'title': info['title'], 'company': info['company'], 'version': info['version']}
    replaced = C.pick_library(C.installed_libraries(), spec) is not None
    log.info('установка %s в репозиторий %s (%s)%s' % (path, C._text(repo.name), C._text(repo.root_folder),
                                                       ' с заменой той же версии' if replaced else ''))
    rec = C.lib_record(lm.install_library(path, repo, True))
    if not (C.lib_matches_identity(rec, spec) and C.version_matches(info['version'], rec['version'])):
        raise C.StepError('установлена не та библиотека: %s' % rec['displayname'])
    found = lm.find_library(rec['displayname'])
    if not found:
        raise C.StepError('после установки find_library(%s) ничего не нашёл' % rec['displayname'], C.EXIT_INTERNAL)
    try:
        file_path = C._text(lm.get_file_path(rec['obj']))
    except Exception:
        file_path = None
    log.info('установлена %s (пространство имён %s), файл %s' % (rec['displayname'], rec['namespace'], file_path))
    return {
        'displayname': rec['displayname'],
        'title': rec['title'],
        'company': rec['company'],
        'version': rec['version'],
        'namespace': rec['namespace'],
        'repository': C._text(found[1].name),
        'repository_root': C._text(found[1].root_folder),
        'file': file_path,
        'compiled': compiled,
        'replaced': replaced,
    }


def run(ctx, step):
    # type: (C.Context, Dict[str, Any]) -> Dict[str, Any]
    log = C.Log(step.get('log'))
    report = I.Report(log)
    result = {
        'ok': False,
        'library': step.get('library'),
        'compiled': None,
        'installed': None,
        'objects': 0,
    }  # type: Dict[str, Any]
    proj = None
    try:
        info = step['info']
        problems = C.library_problems(info)
        if problems:
            raise C.StepError('config.json: %s' % '; '.join(problems))
        lib_path = step['library']
        tmp_project = step['project']
        compiled_path = step.get('compiled')
        log.info('библиотека %s, %s (%s) из %s/src -> %s'
                 % (info['title'], info['version'], info['company'], step['repo_root'], lib_path))
        wanted = scan_library_sources(step['repo_root'], step.get('exclude') or [], step.get('tests_folder') or 'Tests',
                                      log)
        resolved = I.resolve_libraries(step.get('libraries') or [], step.get('repository'), log)
        # библиотека собирается с нуля: исходники — источник истины, правки в IDE не сохраняются.
        # Файл блокировки <путь>.~u проверяется и без самого файла: после остановки CODESYS по
        # таймауту он остаётся и у временного проекта, который так и не был сохранён
        for path in (lib_path, tmp_project):
            C.check_project_lock(path, log)
        for path in (lib_path, compiled_path, tmp_project):
            _remove(path, log)
        C.remove_precompile_cache(lib_path, log)
        C.remove_precompile_cache(tmp_project, log)
        C.ensure_dir(os.path.dirname(os.path.abspath(lib_path)))
        C.ensure_dir(os.path.dirname(os.path.abspath(tmp_project)))
        proj = C.api().projects.create(tmp_project, True)
        actual = set_project_info(proj, info, log)
        libman = proj.get_library_manager()
        I.sync_libraries(libman, resolved, [], log, report)
        warn_unresolved_placeholders(libman, log)
        syncer = I.Syncer(proj, log, report)
        for obj, folder_path in wanted:
            syncer.sync_object(obj, folder_path, {})
        proj.save_as(lib_path)
        if C._norm_path(C._text(proj.path)) != C._norm_path(lib_path):
            raise C.StepError('save_as(%s) сохранил проект в %s' % (lib_path, C._text(proj.path)), C.EXIT_INTERNAL)
        _remove(tmp_project, log)
        check = check_pool(proj, log)
        proj.save()
        result.update({
            'objects': len(wanted),
            'project_info': actual,
            'errors': check['errors'],
            'warnings': check['warnings'],
            'summary_line': check['summary_line'],
            'messages': check['messages'],
            'references': [C._text(r.name) for r in libman.references],
            'installed_libraries': I.installed_from_files(resolved),
            'created': list(report.created),
        })
        if check['errors']:
            result['error'] = ('проверка пула: ошибок %d (см. %s) — библиотека сохранена для разбора в IDE, '
                               'но не компилируется и не устанавливается'
                               % (check['errors'], step.get('log') or 'журнал'))
            return result
        if compiled_path:
            proj.save_as_compiled_library(compiled_path)
            if not os.path.isfile(compiled_path):
                raise C.StepError('save_as_compiled_library не создал %s' % compiled_path, C.EXIT_INTERNAL)
            result['compiled'] = compiled_path
            log.info('скомпилированная библиотека: %s' % compiled_path)
        proj.close()
        proj = None
        target = step.get('install')
        if target:
            use_compiled = bool(target.get('compiled')) and bool(compiled_path)
            result['installed'] = install(compiled_path if use_compiled else lib_path, step.get('repository'), info,
                                          use_compiled, log)
        result['ok'] = True
        return result
    except C.StepError as exc:
        log.error('%s' % exc)
        raise
    except Exception as exc:
        log.error('исключение: %s' % exc)
        raise
    finally:
        if proj is not None:
            try:
                proj.close()
            except Exception:
                pass
        result['log_warnings'] = list(log.warnings)
        if step.get('report'):
            data = dict((k, v) for k, v in result.items())
            data['log_errors'] = list(log.errors)
            try:
                C.write_json(step['report'], data)
            except Exception:
                pass
        log.close()


if __name__ == '__main__':
    C.run_main('library')
