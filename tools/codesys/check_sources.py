# -*- coding: utf-8 -*-
"""Проверка компиляции всех объектов src/ (и tests/) — скрипт CODESYS Scripting (IronPython 2.7).

Запуск — только через tools/codesys/cds.py (python tools/codesys/cds.py check [--tests]).

Зачем: сборка приложения (cds.py build, app.rebuild()) компилирует только объекты, достижимые из
задач. Ошибка в POU, который ни одна задача не вызывает (программа без задачи, ФБ без экземпляра,
метод, функция), в build не видна: «0 ошибок» (проверено на 3.5.17.30, docs/ASSUMPTIONS.md, D34).

Как (проверено зондами на 3.5.17.30, docs/ASSUMPTIONS.md, D38): объекты раскладки создаются в пуле
POU нового проекта без устройства — тем же кодом, что у cds.py library (import_sources.Syncer), —
со ссылками на библиотеки режима, и выполняется proj.check_all_pool_objects() («Проверить все
объекты пула»). Пул компилируется целиком: ошибки в теле и объявлении ФБ без экземпляра, в его
методах, в DUT, который никто не использует, приходят с объектом и позицией. Проект проверки
(job["project"], build/codesys/<имя>-check.project) не сохраняется: projects.create не пишет файл,
проверка пула работает и на несохранённом проекте, а close() отбрасывает изменения; файлы настроек
пользователя (<имя>-*.opt), которые CODESYS пишет при закрытии, удаляются. Прямые адреса
(AT %IX0.0) в GVL и программах в пуле компилируются без ошибок.

Библиотеки — те же, что у проекта build: ссылки режима из config.json и ссылки, которые устройство
(config.json: device) добавляет приложению само (у Control Win V3 — #IoStandard, #3SLicense,
#CAA Device Diagnosis, #BreakpointLogging). Устройство добавляется на время, его ссылки копируются
в пул (mirror_device_libraries), затем оно удаляется: без копий код с IoStandard.IoConfigConnector
давал бы в check «Неизвестный тип», хотя build его собирает, а с устройством в проекте проверка
пула не находит и библиотеки пула (TON — «Неизвестный тип»; проверено зондом на 3.5.17.30).

Persistent Variables скриптом в SP17 не создаются; чтобы обращения к ним проверялись, объект
*.pvl.st создаётся в проверке как GVL с тем же текстом без PERSISTENT (pvl_as_gvl): с PERSISTENT
пул выдаёт предупреждение C0244 «Приложение не содержит VAR_PERSISTENT-списка».

Шаг check: журнал — job["log"] (build/check.log), отчёт — job["report"] (build/check.json).
Ошибки (Error, FatalError) — шаг не пройден (код 1).
"""
from __future__ import absolute_import, print_function, unicode_literals

import os

import cds_common as C
import import_sources as I
import make_library as ML
import stlayout as L

MYPY = False
if MYPY:  # pragma: no cover
    from typing import Any, Dict, List, Optional  # noqa: F401


def pvl_as_gvl(decl):
    # type: (str) -> str
    """Текст Persistent Variables для GVL-заменителя: без ключевого слова PERSISTENT после VAR_GLOBAL.

    Строки и столбцы остальных токенов не меняются (слово заменяется пробелами), поэтому позиции
    сообщений компилятора совпадают со строками файла *.pvl.st.
    """
    tokens = L.tokenize(decl)
    sig = L.significant_indices(tokens)
    drop = set()
    for k, i in enumerate(sig):
        if not tokens[i].is_ident('VAR_GLOBAL'):
            continue
        for j in sig[k + 1:]:
            tok = tokens[j]
            if tok.is_ident('PERSISTENT'):
                drop.add(j)
            elif not tok.is_ident('RETAIN', 'CONSTANT'):
                break
    return ''.join((' ' * len(tok.text)) if i in drop else tok.text for i, tok in enumerate(tokens))


def option_files(project_path):
    # type: (str) -> List[str]
    """Файлы настроек пользователя, которые CODESYS пишет рядом с проектом при закрытии.

    Имена проверены на 3.5.17.30: <имя>-AllUsers.opt и <имя>-<пользователь>-<компьютер>.opt
    (для build/codesys/tpl-check.project — tpl-check-AllUsers.opt, ...).
    """
    folder, name = os.path.split(os.path.abspath(project_path))
    prefix = os.path.splitext(name)[0].lower() + '-'
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(os.path.join(folder, n) for n in names if n.lower().startswith(prefix) and n.lower().endswith('.opt'))


def _copy_flags(new_ref, ref):
    # type: (Any, Any) -> None
    """Пространство имён и qualified_only копии — как у ссылки устройства."""
    namespace = C._attr(ref, 'namespace')
    if namespace and C._text(new_ref.namespace or '') != C._text(namespace):
        new_ref.namespace = namespace
    qualified = C._attr(ref, 'qualified_only')
    if qualified is not None and bool(new_ref.qualified_only) != bool(qualified):
        new_ref.qualified_only = bool(qualified)


def copy_reference(pool_lm, ref):
    # type: (Any, Any) -> Optional[str]
    """Копия ссылки ref (Library Manager приложения) в Library Manager пула; имя копии или None (уже есть).

    Плейсхолдер — add_placeholder(имя, разрешение): в пуле его разрешает библиотека по умолчанию
    (resolution_info «Resolved by placeholder default library»), устройства там нет. Обычная ссылка —
    add_library(библиотека репозитория или имя ссылки).
    """
    rec = C.ref_record(ref)
    pool = [C.ref_record(x) for x in pool_lm.references]
    if rec['placeholder']:
        name = rec['placeholder']
        if any((r['placeholder'] or '').lower() == name.lower() for r in pool):
            return None
        target = C._text(C._attr(ref, 'effective_resolution') or C._attr(ref, 'default_resolution') or rec['target'])
        if not target:
            raise C.StepError('плейсхолдер #%s устройства ни во что не разрешается' % name)
        pool_lm.add_placeholder(name, target)
        new = [r['obj'] for r in (C.ref_record(x) for x in pool_lm.references)
               if (r['placeholder'] or '').lower() == name.lower()]
        label = '#%s -> %s' % (name, target)
    else:
        name = rec['name']
        if any(not r['placeholder'] and r['name'].lower() == name.lower() for r in pool):
            return None
        managed = rec['library']['obj'] if rec.get('library') else None
        pool_lm.add_library(managed if managed is not None else name)
        new = [r['obj'] for r in (C.ref_record(x) for x in pool_lm.references)
               if not r['placeholder'] and r['name'].lower() == name.lower()]
        label = name
    if not new:
        raise C.StepError('ссылка %s не появилась в Library Manager пула' % label)
    _copy_flags(new[0], ref)
    return label


def mirror_device_libraries(proj, device, log):
    # type: (Any, Optional[Dict[str, Any]], C.Log) -> List[str]
    """Ссылки, которые устройство добавляет приложению само, — в Library Manager пула проекта проверки.

    Устройство (config.json: device) добавляется на время: ссылки Library Manager его приложения
    (плейсхолдеры #IoStandard, #3SLicense, ... — у каждого ПЛК свои) копируются в пул с тем же
    разрешением, пространством имён и qualified_only, затем устройство удаляется: с устройством в
    проекте проверка пула не находит и библиотеки пула (проверено зондом на 3.5.17.30). Если
    устройство не добавляется (нет его описания) — предупреждение, проверка идёт без его библиотек
    (build в этом случае тоже не пройдёт). Возвращает имена скопированных ссылок.
    """
    if not device:
        return []
    try:
        device_id = C.api().DeviceID(int(device['type']), C._text(device['id']), C._text(device['version']))
        proj.add(C._text(device.get('name') or 'Device'), device_id)
    except Exception as exc:
        log.warn('устройство %s / %s / %s не добавлено (%s): библиотек, которые добавляет устройство, в проверке нет'
                 % (device.get('type'), device.get('id'), device.get('version'), C.squash_ws(C._text(exc))))
        return []
    copied = []  # type: List[str]
    try:
        app = proj.active_application
        app_lm = I.find_library_manager(app) if app is not None else None
        pool_lm = proj.get_library_manager()
        for ref in (list(app_lm.references) if app_lm is not None else []):
            try:
                label = copy_reference(pool_lm, ref)
            except Exception as exc:
                log.warn('ссылка устройства %s в проверку не скопирована: %s'
                         % (C._text(C._attr(ref, 'name') or '?'), C.squash_ws(C._text(exc))))
                continue
            if label:
                copied.append(label)
    finally:
        dev = C.find_device(proj)
        if dev is not None:
            dev.remove()
    if C.find_device(proj) is not None:
        raise C.StepError('устройство не удалено из проекта проверки', C.EXIT_INTERNAL)
    log.info('ссылки устройства в проверке: %s' % (', '.join(copied) or 'нет'))
    return copied


def create_pvl_standin(syncer, obj, folder_path, log, report):
    # type: (Any, L.StObject, List[str], C.Log, I.Report) -> None
    parent = syncer.folder(folder_path)
    gvl = parent.create_gvl(obj.name)
    gvl.textual_declaration.replace(pvl_as_gvl(obj.decl))
    report.add('created', 'GVL %s (вместо Persistent Variables %s)' % (obj.name, obj.main_path()))
    log.info('%s: Persistent Variables проверяются как GVL без PERSISTENT (в SP17 скриптом не создаются)'
             % obj.main_path())


def run(ctx, step):
    # type: (C.Context, Dict[str, Any]) -> Dict[str, Any]
    log = C.Log(step.get('log'))
    report = I.Report(log)
    result = {
        'ok': False,
        'project': step.get('project'),
        'mode': step.get('mode'),
        'with_tests': bool(step.get('with_tests')),
        'objects': 0,
    }  # type: Dict[str, Any]
    proj = None
    tmp_project = step['project']
    try:
        repo_root = step['repo_root']
        with_tests = bool(step.get('with_tests'))
        tests_folder = step.get('tests_folder') or 'Tests'
        log.info('проверка всех объектов: репозиторий %s, режим %s, тесты %s' % (repo_root, step.get('mode'),
                                                                                  with_tests))
        wanted = I.scan_sources(repo_root, with_tests, tests_folder, log)
        if not wanted:
            raise C.StepError('в src/ нет объектов для проверки')
        resolved = I.resolve_libraries(step.get('libraries') or [], step.get('repository'), log)
        # проект проверки создаётся с нуля и не сохраняется; файл блокировки <путь>.~u мог остаться
        # после остановки CODESYS по таймауту
        C.check_project_lock(tmp_project, log)
        if os.path.exists(tmp_project):
            os.remove(tmp_project)
        C.remove_precompile_cache(tmp_project, log)
        C.ensure_dir(os.path.dirname(os.path.abspath(tmp_project)))
        proj = C.api().projects.create(tmp_project, True)
        device_libraries = mirror_device_libraries(proj, step.get('device'), log)
        libman = proj.get_library_manager()
        I.sync_libraries(libman, resolved, [], log, report)
        syncer = I.Syncer(proj, log, report)
        for obj, folder_path in wanted:
            if obj.kind == L.KIND_PVL:
                create_pvl_standin(syncer, obj, folder_path, log, report)
            else:
                syncer.sync_object(obj, folder_path, {})
        check = ML.check_pool(proj, log)
        log.info('итог: объектов %d, ошибок %d, предупреждений %d' % (len(wanted), check['errors'],
                                                                       check['warnings']))
        result.update({
            'ok': check['errors'] == 0,
            'objects': len(wanted),
            'errors': check['errors'],
            'warnings': check['warnings'],
            'summary_line': check['summary_line'],
            'messages': check['messages'],
            'references': [C._text(r.name) for r in libman.references],
            'device_libraries': device_libraries,
            'installed_libraries': I.installed_from_files(resolved),
        })
        if check['errors']:
            result['error'] = 'проверка всех объектов: ошибок %d (см. %s)' % (check['errors'],
                                                                           step.get('log') or 'журнал')
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
                proj.close()  # без сохранения: изменения отбрасываются
            except Exception:
                pass
        for path in [tmp_project] + option_files(tmp_project):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
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
    C.run_main('check')
