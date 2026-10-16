# -*- coding: utf-8 -*-
"""Импорт раскладки src/ (и tests/) в проект CODESYS — скрипт CODESYS Scripting (IronPython 2.7).

Запуск — только через tools/codesys/cds.py (python tools/codesys/cds.py import [--tests]):
он пишет файл задания (путь — в переменной окружения CDS_JOB) и запускает
CODESYS.exe --noUI --runscript=<этот файл>.

Что делает шаг import:
1. Читает src/ (и tests/ с флагом) через stlayout.scan; ошибки раскладки — отказ без изменений.
2. Открывает проект или создаёт его: устройство (config.json: device), приложение.
3. Идемпотентно создаёт или обновляет DUT, GVL, интерфейсы (методы, свойства; объявление
   интерфейса по умолчанию 'EXTENDS __System.IQueryInterface' заменяется текстом файла), POU с
   методами и свойствами (аксессоры Get/Set — ровно как в раскладке, лишние удаляются), папки
   (подкаталоги src/ — папки проекта, tests/ — папка Tests). Текст меняется, только если он
   отличается: повторный импорт без правок ничего не меняет. Имя, отличающееся от раскладки
   только регистром (объект, метод, свойство, папка), переименовывается.
   Перед открытием проекта удаляется кэш предкомпиляции (cds_common.remove_precompile_cache):
   с ним сборка после замены объявления POU с методами могла видеть старый текст.
4. Удаляет объекты управляемых видов (POU, DUT, GVL, интерфейсы, методы и свойства POU),
   которых больше нет в исходниках, и опустевшие папки — с записью в отчёт.
5. Конфигурация задач и ссылки на библиотеки — по режиму (normal/test) из config.json. Библиотеки
   ищутся в репозиториях CODESYS до открытия проекта (точная версия или новейшая '*'); нет
   нужной — установка из install_from, иначе отказ со списком missing_libraries (по нему
   cds.py собирает библиотеки из соседних репозиториев). Ссылка другой версии заменяется,
   пространство имён ссылки — из config.json, плейсхолдер — с перенаправлением.
6. Сохраняет проект. Журнал — job["log"] (build/import.log), отчёт — job["report"] (build/import.json).
"""
from __future__ import absolute_import, print_function, unicode_literals

import os

import cds_common as C
import stlayout as L

MYPY = False
if MYPY:  # pragma: no cover
    from typing import Any, Dict, List, Optional, Tuple  # noqa: F401


class Report(object):
    """Изменения проекта за шаг импорта."""

    def __init__(self, log):
        # type: (C.Log) -> None
        self.log = log
        self.created = []  # type: List[str]
        self.updated = []  # type: List[str]
        self.removed = []  # type: List[str]
        self.moved = []  # type: List[str]
        self.unchanged = 0

    def add(self, bucket, what):
        # type: (str, str) -> None
        getattr(self, bucket).append(what)
        self.log.info('%s: %s' % (bucket, what))

    @property
    def changes(self):
        # type: () -> int
        return len(self.created) + len(self.updated) + len(self.removed) + len(self.moved)

    def as_dict(self):
        # type: () -> Dict[str, Any]
        return {
            'created': self.created,
            'updated': self.updated,
            'removed': self.removed,
            'moved': self.moved,
            'unchanged': self.unchanged,
            'changes': self.changes,
        }


# ---------------------------------------------------------------------------
# Чтение раскладки
# ---------------------------------------------------------------------------


def scan_sources(repo_root, with_tests, tests_folder, log):
    # type: (str, bool, str, C.Log) -> List[Tuple[L.StObject, List[str]]]
    """Объекты раскладки с путём папки в проекте: [(объект, [папка, ...])]."""
    wanted = []  # type: List[Tuple[L.StObject, List[str]]]
    subdirs = [('src', [])]  # type: List[Tuple[str, List[str]]]
    if with_tests:
        subdirs.append(('tests', [tests_folder]))
    failed = False
    for subdir, prefix in subdirs:
        result = L.scan(repo_root, subdir)
        for issue in result.issues:
            text = issue.format()
            if issue.severity == 'error':
                log.error(text)
                failed = True
            else:
                log.warn(text)
        for obj in result.objects:
            if subdir == 'src' and obj.folder and obj.folder[0].lower() == tests_folder.lower():
                log.error(
                    '%s: папка верхнего уровня %s в src/ зарезервирована под tests/' % (obj.main_path(), tests_folder)
                )
                failed = True
            wanted.append((obj, prefix + list(obj.folder)))
        log.info('%s/: объектов %d, замечаний %d' % (subdir, len(result.objects), len(result.issues)))
    seen = {}  # type: Dict[str, L.StObject]
    for obj, _ in wanted:
        key = obj.name.lower()
        if key in seen:
            log.error(
                "объект '%s' объявлен дважды: %s и %s (имена CODESYS без учёта регистра)"
                % (obj.name, seen[key].main_path(), obj.main_path())
            )
            failed = True
        seen[key] = obj
    if failed:
        raise C.StepError('ошибки раскладки исходников (см. %s) — проект не изменён' % (log.path or 'журнал'))
    return wanted


# ---------------------------------------------------------------------------
# Синхронизация объектов
# ---------------------------------------------------------------------------


def _set_text(doc, text):
    # type: (Any, str) -> bool
    """Заменяет текст документа, если он отличается. True — текст изменён."""
    current = C._text(doc.text)
    if current == text:
        return False
    doc.replace(text)
    return True


def _header_keyword(text):
    # type: (Optional[str]) -> Optional[str]
    hdr = L.parse_header(text or '')
    return hdr.keyword if hdr is not None else None


class Syncer(object):
    def __init__(self, app, log, report):
        # type: (Any, C.Log, Report) -> None
        self.app = app
        self.log = log
        self.report = report
        self.se = C.api()
        self._folders = {}  # type: Dict[Tuple[str, ...], Any]
        self._renamed = set()  # type: set

    # --- обход проекта ---------------------------------------------------

    def existing_objects(self):
        # type: () -> Dict[str, Tuple[Any, str, List[str]]]
        """Объекты управляемых видов в приложении: имя (нижний регистр) -> (объект, вид, папка)."""
        found = {}  # type: Dict[str, Tuple[Any, str, List[str]]]

        def walk(parent, path):
            # type: (Any, List[str]) -> None
            for obj in C.children(parent):
                kind = C.kind_of(obj)
                if kind == C.K_FOLDER:
                    walk(obj, path + [C.obj_name(obj)])
                elif kind in C.MANAGED_KINDS:
                    found[C.obj_name(obj).lower()] = (obj, kind, list(path))

        walk(self.app, [])
        return found

    def folder(self, path):
        # type: (List[str]) -> Any
        """Папка проекта по пути (создаётся при необходимости); [] — само приложение."""
        key = tuple(p.lower() for p in path)
        if not path:
            return self.app
        if key in self._folders:
            return self._folders[key]
        parent = self.folder(path[:-1])
        name = path[-1]
        found = C.find_child(parent, name, (C.K_FOLDER,))
        if found is None:
            parent.create_folder(name)
            found = C.find_child(parent, name, (C.K_FOLDER,))
            if found is None:
                raise C.StepError("не удалось создать папку '%s'" % '/'.join(path))
            self.report.add('created', 'FOLDER %s' % '/'.join(path))
        elif C.obj_name(found) != name:
            # имена CODESYS без учёта регистра: подкаталог переименован только регистром
            old = C.obj_name(found)
            found.rename(name)
            self.report.add('updated', 'FOLDER %s (имя: %s)' % ('/'.join(path), old))
        self._folders[key] = found
        return found

    # --- регистр имён ------------------------------------------------------

    def fix_name_case(self, wanted, existing):
        # type: (List[Tuple[L.StObject, List[str]]], Dict[str, Tuple[Any, str, List[str]]]) -> None
        """Регистр имён объектов, методов и свойств — как в раскладке (до синхронизации текстов).

        Поиск в проекте идёт без учёта регистра (как в CODESYS), поэтому переименование
        файла только регистром (FB_example -> FB_Example) без этого шага не дошло бы до
        проекта, и export вернул бы старое имя файла.
        """
        for obj, _ in wanted:
            entry = existing.get(obj.name.lower())
            if entry is None or entry[1] != obj.kind:
                continue  # новый объект или будет пересоздан
            cur = entry[0]
            old = C.obj_name(cur)
            if old != obj.name:
                cur.rename(obj.name)
                self._renamed.add(obj.name.lower())
                self.report.add('updated', '%s %s (имя: %s)' % (obj.kind.upper(), obj.name, old))
            if obj.kind not in (L.KIND_POU, L.KIND_ITF):
                continue
            names = {}  # type: Dict[Tuple[str, str], str]
            for method in obj.methods:
                names[(C.K_METHOD, method.name.lower())] = method.name
            for prop in obj.properties:
                names[(C.K_PROPERTY, prop.name.lower())] = prop.name
            for child in C.children(cur):
                kind = C.kind_of(child)
                old_member = C.obj_name(child)
                new_member = names.get((kind, old_member.lower()))
                if new_member is not None and new_member != old_member:
                    child.rename(new_member)
                    self._renamed.add(obj.name.lower())
                    self.report.add('updated', '%s %s.%s (имя: %s)' % (kind.upper(), obj.name, new_member, old_member))

    # --- создание --------------------------------------------------------

    def create(self, obj, parent):
        # type: (L.StObject, Any) -> Any
        se = self.se
        hdr = obj.header
        if obj.kind == L.KIND_DUT:
            kind = hdr.type_kind if hdr is not None else None
            if kind == 'alias':
                td = L.parse_type_decl(obj.decl)
                base = (td.alias_type if td is not None else None) or 'INT'
                return parent.create_dut(obj.name, se.DutType.Alias, base)
            dut_type = {
                'struct': se.DutType.Structure,
                'enum': se.DutType.Enumeration,
                'union': se.DutType.Union,
            }.get(kind, se.DutType.Structure)
            return parent.create_dut(obj.name, dut_type)
        if obj.kind == L.KIND_GVL:
            return parent.create_gvl(obj.name)
        if obj.kind == L.KIND_PVL:
            # В SP17 нет create_persistentvars (проверено: AttributeError) — ручной шаг
            return None
        if obj.kind == L.KIND_ITF:
            return parent.create_interface(obj.name)
        if obj.kind == L.KIND_POU:
            if obj.pou_kind == L.POU_PROGRAM:
                return parent.create_pou(name=obj.name, type=se.PouType.Program)
            if obj.pou_kind == L.POU_FUNCTION:
                return_type = (hdr.return_type if hdr is not None else None) or 'INT'
                return parent.create_pou(name=obj.name, type=se.PouType.Function, return_type=return_type)
            return parent.create_pou(name=obj.name, type=se.PouType.FunctionBlock)
        raise C.StepError('неизвестный вид объекта %s' % obj.kind)

    def needs_recreate(self, cur, cur_kind, obj):
        # type: (Any, str, L.StObject) -> Optional[str]
        """Причина пересоздания существующего объекта или None."""
        if cur_kind != obj.kind:
            return 'вид %s -> %s' % (cur_kind, obj.kind)
        if obj.kind == L.KIND_POU:
            keyword = _header_keyword(C.decl_text(cur))
            wanted = obj.header.keyword if obj.header is not None else None
            if keyword != wanted:
                return 'тип POU %s -> %s' % (keyword, wanted)
            if not C.has_impl(cur):
                return 'реализация не на ST'
        if not C.has_decl(cur):
            return 'нет текстового объявления'
        return None

    def sync_object(self, obj, folder_path, existing):
        # type: (L.StObject, List[str], Dict[str, Tuple[Any, str, List[str]]]) -> None
        label = '%s %s' % (obj.kind.upper(), obj.name)
        parent = self.folder(folder_path)
        entry = existing.get(obj.name.lower())
        cur = None
        if entry is not None:
            cur, cur_kind, cur_path = entry
            reason = self.needs_recreate(cur, cur_kind, obj)
            if reason is not None:
                cur.remove()
                self.report.add('removed', '%s (пересоздание: %s)' % (label, reason))
                cur = None
            elif [p.lower() for p in cur_path] != [p.lower() for p in folder_path]:
                cur.move(parent, -1)
                where = (label, '/'.join(cur_path) or '.', '/'.join(folder_path) or '.')
                self.report.add('moved', '%s: %s -> %s' % where)
        if cur is None:
            cur = self.create(obj, parent)
            if cur is None:
                self.log.warn(
                    '%s: Persistent Variables скриптом SP17 не создаются — создайте объект %s вручную '
                    '(docs/MANUAL_STEPS.md), при следующем импорте текст обновится' % (obj.main_path(), obj.name)
                )
                return
            self.report.add('created', label)
            created = True
        else:
            created = False
        changed = []  # type: List[str]
        if _set_text(cur.textual_declaration, obj.decl):
            changed.append('decl')
        if obj.kind == L.KIND_POU and _set_text(cur.textual_implementation, obj.impl or ''):
            changed.append('impl')
        if obj.kind in (L.KIND_POU, L.KIND_ITF):
            changed.extend(self.sync_members(cur, obj))
        if created:
            return
        if changed:
            self.report.add('updated', '%s (%s)' % (label, ', '.join(changed)))
        elif obj.name.lower() not in self._renamed:
            self.report.unchanged += 1

    # --- методы и свойства ----------------------------------------------

    def sync_members(self, cur, obj):
        # type: (Any, L.StObject) -> List[str]
        is_itf = obj.kind == L.KIND_ITF
        changed = []  # type: List[str]
        members = {}  # type: Dict[str, Tuple[Any, str]]
        for child in C.children(cur):
            kind = C.kind_of(child)
            if kind in (C.K_METHOD, C.K_PROPERTY):
                members[C.obj_name(child).lower()] = (child, kind)
            elif kind in (C.K_ACTION, C.K_TRANSITION):
                self.log.warn(
                    '%s.%s: %s не входит в раскладку — остаётся в проекте, но не экспортируется'
                    % (obj.name, C.obj_name(child), kind)
                )
        wanted = {}  # type: Dict[str, str]
        for method in obj.methods:
            wanted[method.name.lower()] = C.K_METHOD
        for prop in obj.properties:
            wanted[prop.name.lower()] = C.K_PROPERTY
        for key, (child, kind) in sorted(members.items()):
            if wanted.get(key) != kind:
                child.remove()
                del members[key]
                self.report.add('removed', '%s %s.%s' % (kind.upper(), obj.name, C.obj_name(child)))
                changed.append('-' + C.obj_name(child))
        for method in obj.methods:
            entry = members.get(method.name.lower())
            label = 'METHOD %s.%s' % (obj.name, method.name)
            if entry is None:
                hdr = method.header
                return_type = hdr.return_type if hdr is not None else None
                child = cur.create_method(method.name, return_type)
                self.report.add('created', label)
                changed.append('+' + method.name)
            else:
                child = entry[0]
            parts = []  # type: List[str]
            if _set_text(child.textual_declaration, method.decl):
                parts.append('decl')
            if not is_itf and C.has_impl(child) and _set_text(child.textual_implementation, method.impl or ''):
                parts.append('impl')
            if parts and entry is not None:
                self.report.add('updated', '%s (%s)' % (label, ', '.join(parts)))
                changed.append(method.name)
        for prop in obj.properties:
            entry = members.get(prop.name.lower())
            child = self.sync_property(cur, obj, prop, entry[0] if entry is not None else None, is_itf)
            if child is not None:
                changed.append(prop.name)
        return changed

    def sync_property(self, cur, obj, prop, child, is_itf):
        # type: (Any, L.StObject, L.StProperty, Any, bool) -> Any
        """Создаёт или обновляет свойство; возвращает объект, если что-то изменилось."""
        label = 'PROPERTY %s.%s' % (obj.name, prop.name)
        wanted = {ACC_GET: prop.has_get, ACC_SET: prop.has_set}
        if child is not None:
            accessors = dict((C.obj_name(a), a) for a in C.children(child) if C.kind_of(a) == C.K_ACCESSOR)
            missing = [name for name, need in sorted(wanted.items()) if need and name not in accessors]
            if missing:
                # отдельно аксессор скриптом не создаётся: пересоздаём свойство (появятся оба)
                child.remove()
                self.report.add('removed', '%s (пересоздание: нет аксессора %s)' % (label, ', '.join(missing)))
                child = None
        created = child is None
        if created:
            hdr = prop.header
            return_type = (hdr.return_type if hdr is not None else None) or 'INT'
            child = cur.create_property(prop.name, return_type)
            self.report.add('created', label)
        parts = []  # type: List[str]
        if _set_text(child.textual_declaration, prop.decl):
            parts.append('decl')
        accessors = dict((C.obj_name(a), a) for a in C.children(child) if C.kind_of(a) == C.K_ACCESSOR)
        for name in (ACC_GET, ACC_SET):
            acc = accessors.get(name)
            if acc is None:
                continue
            if not wanted[name]:
                acc.remove()
                if created:  # create_property создаёт оба аксессора — лишний убираем без записи в отчёт
                    self.log.info('ACCESSOR %s.%s.%s удалён (нет в раскладке)' % (obj.name, prop.name, name))
                else:
                    self.report.add('removed', 'ACCESSOR %s.%s.%s' % (obj.name, prop.name, name))
                    parts.append('-' + name)
                continue
            if name == ACC_GET:
                acc_decl, acc_impl = prop.get_decl, prop.get_impl
            else:
                acc_decl, acc_impl = prop.set_decl, prop.set_impl
            if acc_decl is None:
                acc_decl = '' if is_itf else C.DEFAULT_ACCESSOR_DECL
            if C.has_decl(acc) and _set_text(acc.textual_declaration, acc_decl):
                parts.append(name + '.decl')
            if not is_itf and C.has_impl(acc) and _set_text(acc.textual_implementation, acc_impl or ''):
                parts.append(name + '.impl')
        if parts and not created:
            self.report.add('updated', '%s (%s)' % (label, ', '.join(parts)))
        return child if (parts or created) else None

    # --- удаление лишнего ---------------------------------------------------

    def remove_stale(self, wanted_names, existing):
        # type: (Dict[str, L.StObject], Dict[str, Tuple[Any, str, List[str]]]) -> None
        for key in sorted(existing):
            if key in wanted_names:
                continue
            cur, kind, path = existing[key]
            where = '/'.join(path) or '.'
            name = C.obj_name(cur)
            cur.remove()
            self.report.add('removed', '%s %s (папка %s: нет в исходниках)' % (kind.upper(), name, where))
            del existing[key]

    def remove_empty_folders(self, wanted_paths):
        # type: (set) -> None
        def walk(parent, path):
            # type: (Any, List[str]) -> None
            for obj in C.children(parent):
                if C.kind_of(obj) != C.K_FOLDER:
                    continue
                sub = path + [C.obj_name(obj)]
                walk(obj, sub)
                if C.children(obj):
                    continue
                if tuple(p.lower() for p in sub) in wanted_paths:
                    continue
                obj.remove()
                self._folders.pop(tuple(p.lower() for p in sub), None)
                self.report.add('removed', 'FOLDER %s (пустая)' % '/'.join(sub))

        walk(self.app, [])


ACC_GET = C.ACCESSOR_GET
ACC_SET = C.ACCESSOR_SET


# ---------------------------------------------------------------------------
# Задачи и библиотеки
# ---------------------------------------------------------------------------


def _task_pou_names(task):
    # type: (Any) -> List[str]
    names = []  # type: List[str]
    pous = task.pous
    for i in range(len(pous)):
        item = pous[i]
        if isinstance(item, C.STRING_TYPES):
            names.append(C._text(item))
        else:
            names.append(C._text(item[0]))
    return names


def sync_tasks(app, tasks_cfg, log, report):
    # type: (Any, List[Dict[str, Any]], C.Log, Report) -> None
    tc = None
    for obj in C.children(app):
        try:
            if obj.is_task_configuration:
                tc = obj
                break
        except Exception:
            continue
    if tc is None:
        tc = app.create_task_configuration()
        report.add('created', 'TASK_CONFIGURATION')
    existing = {}  # type: Dict[str, Any]
    for obj in C.children(tc):
        try:
            if obj.is_task:
                existing[C.obj_name(obj).lower()] = obj
        except Exception:
            continue
    wanted = set()
    for cfg in tasks_cfg:
        name = cfg['name']
        wanted.add(name.lower())
        task = existing.get(name.lower())
        created = task is None
        if created:
            task = tc.create_task(name)
            report.add('created', 'TASK %s' % name)
        parts = []  # type: List[str]
        ms = float(cfg['interval_ms'])
        try:
            unit = task.interval_unit
        except Exception:
            unit = None
        if C.interval_ms(task.interval, unit) != ms:
            task.interval = '%d' % int(ms) if ms == int(ms) else '%s' % ms
            try:
                task.interval_unit = 'ms'
            except Exception:
                pass
            parts.append('interval=%sms' % cfg['interval_ms'])
        if cfg.get('priority') is not None and C._text(task.priority) != '%s' % cfg['priority']:
            task.priority = '%s' % cfg['priority']
            parts.append('priority=%s' % cfg['priority'])
        want_pous = [C._text(p) for p in cfg.get('pous', [])]
        if [p.lower() for p in _task_pou_names(task)] != [p.lower() for p in want_pous]:
            while len(task.pous):
                task.pous.remove(0)
            for pou in want_pous:
                task.pous.add(pou)
            parts.append('pous=%s' % ','.join(want_pous))
        if parts and not created:
            report.add('updated', 'TASK %s (%s)' % (name, '; '.join(parts)))
        elif parts:
            log.info('TASK %s: %s' % (name, '; '.join(parts)))
        else:
            report.unchanged += 1
    for key in sorted(existing):
        if key not in wanted:
            existing[key].remove()
            report.add('removed', 'TASK %s (нет в config.json для этого режима)' % C.obj_name(existing[key]))


def _label(spec):
    # type: (Dict[str, Any]) -> str
    return C._text(spec.get('label') or spec.get('key') or spec.get('namespace') or '?')


def _pin(spec):
    # type: (Dict[str, Any]) -> str
    return C.VERSION_NEWEST if C.is_newest_pin(spec.get('version')) else C._text(spec.get('version'))


def install_from_file(spec, repository, log):
    # type: (Dict[str, Any], Optional[str], C.Log) -> Dict[str, Any]
    """Установка библиотеки из spec['install_from'] в репозиторий; запись установленной библиотеки."""
    path = spec.get('install_from')
    label = _label(spec)
    if not path or not os.path.isfile(path):
        # без этой проверки install_library отвечает непонятным «Не удалось открыть управляемую
        # библиотеку (Ссылка на объект не указывает на экземпляр объекта)» (проверено на 3.5.17.30)
        where = spec.get('install_env') or 'config.json'
        raise C.StepError('файл библиотеки %s не найден: %s (%s)' % (label, path, where), C.EXIT_INTERNAL)
    repo = C.find_repository(repository)
    log.info('установка библиотеки %s из %s в репозиторий %s' % (label, path, C._text(repo.name)))
    rec = C.lib_record(C.api().librarymanager.install_library(path, repo, True))
    if not (C.lib_matches_identity(rec, spec) and C.version_matches(spec.get('version'), rec['version'])):
        raise C.StepError(
            'установленная из %s библиотека %s (пространство имён %s) не соответствует config.json: '
            'libraries.%s (версия %s)' % (path, rec['displayname'], rec['namespace'], spec.get('key'), _pin(spec))
        )
    rec['installed_from'] = path
    return rec


def resolve_libraries(specs, repository, log, install=True):
    # type: (List[Dict[str, Any]], Optional[str], C.Log, bool) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]
    """Библиотеки из config.json в репозиториях CODESYS: [(spec, запись установленной библиотеки)].

    Версия — точная или новейшая ('*'). Нет подходящей — установка из install_from (если задан)
    в репозиторий repository. Найденная библиотека проверяется и по её собственным зависимостям
    (рекурсивно, C.missing_dependencies): без них CODESYS не соберёт потребителя. Остальные
    отсутствующие (и библиотеки без своих зависимостей) — одна StepError (код 3) со списком
    missing_libraries: по нему cds.py собирает библиотеки из соседних репозиториев (build_from_repo;
    сборка библиотеки там же ставит и её зависимости) и повторяет шаг. Проект при этом не меняется:
    разрешение идёт до открытия проекта.
    """
    if not specs:
        return []
    records = C.installed_libraries()
    resolved = []  # type: List[Tuple[Dict[str, Any], Dict[str, Any]]]
    missing = []  # type: List[str]
    keys = []  # type: List[str]
    for spec in specs:
        rec = C.pick_library(records, spec)
        if rec is None and install and spec.get('install_from'):
            rec = install_from_file(spec, repository, log)
            records = C.installed_libraries()
        absent = C.missing_dependencies(rec, records) if rec is not None else []
        if rec is None or absent:
            hint = []
            if rec is None:
                versions = sorted(set(r['version'] for r in records if C.lib_matches_identity(r, spec)),
                                  key=lambda v: C.parse_version(v) or (0,))
                what = ('установлены версии: %s' % ', '.join(versions)) if versions else 'не установлена ни одна версия'
            else:
                what = 'установлена %s, но в репозиториях нет её зависимостей: %s' % (rec['displayname'],
                                                                                     ', '.join(absent))
            if spec.get('build_from_repo'):
                hint.append('cds.py deps соберёт её из %s' % spec['build_from_repo'])
            where = spec.get('install_env') or 'libraries.%s.install_from' % spec.get('key')
            hint.append('путь к .library — в %s' % where)
            missing.append('%s %s (%s; %s)' % (_label(spec), _pin(spec), what, '; '.join(hint)))
            keys.append(C._text(spec.get('key')))
            continue
        log.info('библиотека %s %s: %s' % (C._text(spec.get('key') or _label(spec)), _pin(spec), rec['displayname']))
        resolved.append((spec, rec))
    if missing:
        raise C.StepError(
            'нет библиотек в репозиториях CODESYS: %s (docs/MANUAL_STEPS.md, раздел 7)' % '; '.join(missing),
            C.EXIT_INTERNAL,
            data={'missing_libraries': keys},
        )
    return resolved


def installed_from_files(resolved):
    # type: (List[Tuple[Dict[str, Any], Dict[str, Any]]]) -> List[str]
    """Библиотеки, которые resolve_libraries поставил из install_from (их печатает cds.py)."""
    return ['%s <- %s' % (rec['displayname'], rec['installed_from'])
            for _, rec in resolved if rec.get('installed_from')]


def find_library_manager(container):
    # type: (Any) -> Any
    """Library Manager приложения или пула POU библиотеки (создаётся, если его нет)."""
    for obj in C.children(container):
        try:
            if obj.is_libman:
                return obj
        except Exception:
            continue
    return container.get_library_manager()


def _find_ref(libman, predicate):
    # type: (Any, Any) -> Any
    for ref in libman.references:
        if predicate(C.ref_record(ref)):
            return ref
    return None


def _fix_reference(ref, spec):
    # type: (Any, Dict[str, Any]) -> List[str]
    """Пространство имён и qualified_only ссылки — как в config.json; список изменений."""
    changes = []  # type: List[str]
    namespace = spec.get('namespace')
    if namespace and C._text(ref.namespace or '') != namespace:
        ref.namespace = namespace
        changes.append('namespace=%s' % namespace)
    qualified = spec.get('qualified_only')
    if qualified is not None and bool(ref.qualified_only) != bool(qualified):
        ref.qualified_only = bool(qualified)
        changes.append('qualified_only=%s' % bool(qualified))
    return changes


def add_reference(libman, spec, rec, want, log):
    # type: (Any, Dict[str, Any], Dict[str, Any], str, C.Log) -> Any
    """Добавляет ссылку на библиотеку rec так, как требует spec (проверено на 3.5.17.30).

    - точная версия: add_library(ManagedLib) — ссылка 'T, 1.0.0.0 (C)';
    - '*': add_library('T, * (C)') — ссылка на новейшую установленную версию;
    - placeholder: add_placeholder(имя, 'T, <версия|*> (C)'). Своё имя плейсхолдера ни
      устройство, ни профиль библиотек не разрешают, и разрешение по умолчанию в приложении не
      работает («Библиотека ... не добавлена в Менеджер библиотек») — тогда ставится
      перенаправление set_redirection на то же имя. Перенаправление хранится в проекте отдельно
      от ссылки и переживает её удаление: новый плейсхолдер с тем же именем сразу разрешается
      старым перенаправлением (другой версией) — поэтому уже перенаправленный плейсхолдер тоже
      перенаправляется на want. Плейсхолдер, который разрешает профиль (например, Standard), не
      перенаправляется.
    """
    placeholder = spec.get('placeholder')
    if placeholder:
        libman.add_placeholder(placeholder, want)
        ref = _find_ref(libman, lambda r: (r['placeholder'] or '').lower() == placeholder.lower())
        if ref is None:
            raise C.StepError('плейсхолдер #%s не появился в Library Manager после add_placeholder' % placeholder)
        try:
            redirection = C._text(ref.get_redirection() or '')
        except Exception:
            redirection = ''
        unresolved = not C._attr(ref, 'effective_resolution')
        if (unresolved or C._attr(ref, 'is_redirected')) and redirection.lower() != want.lower():
            ref.set_redirection(want)
            why = 'не разрешается устройством и профилем' if unresolved else 'было перенаправление на %s' % redirection
            log.info('плейсхолдер #%s %s — перенаправление на %s' % (placeholder, why, want))
    else:
        if C.is_newest_pin(spec.get('version')):
            libman.add_library(want)
        else:
            libman.add_library(rec['obj'])
        ref = _find_ref(libman, lambda r: not r['placeholder'] and r['name'].lower() == want.lower())
        if ref is None:
            raise C.StepError('ссылка %s не появилась в Library Manager после add_library' % want)
    _fix_reference(ref, spec)
    return ref


def sync_libraries(libman, resolved, other_specs, log, report):
    # type: (Any, List[Tuple[Dict[str, Any], Dict[str, Any]]], List[Dict[str, Any]], C.Log, Report) -> None
    """Ссылки Library Manager — как в config.json.

    Ссылка на ту же библиотеку другой версии (или другого вида: плейсхолдер / обычная)
    заменяется; совпадающая остаётся (пространство имён и qualified_only выравниваются);
    ссылки на библиотеки других режимов удаляются. Прочие ссылки (системные плейсхолдеры
    устройства, добавленные вручную) не трогаются.
    """
    for spec, rec in resolved:
        label = 'LIBRARY %s' % _label(spec)
        want = C.spec_reference(spec, rec)
        mine = [r for r in (C.ref_record(x) for x in libman.references) if C.ref_matches_identity(r, spec)]
        current = [r for r in mine if C.ref_is_current(r, spec, want)]
        keep = current[0] if current else None
        for ref in mine:
            if ref is keep:
                continue
            libman.remove_library(ref['name'])
            report.add('removed', '%s (%s: заменяется на %s)' % (label, ref['name'], want))
        if keep is None:
            add_reference(libman, spec, rec, want, log)
            prefix = ('#%s -> ' % spec['placeholder']) if spec.get('placeholder') else ''
            report.add('created', '%s (%s%s)' % (label, prefix, want))
            continue
        changes = _fix_reference(keep['obj'], spec)
        if changes:
            report.add('updated', '%s (%s)' % (label, ', '.join(changes)))
        else:
            report.unchanged += 1
    wanted_specs = [spec for spec, _ in resolved]
    for spec in other_specs:
        for ref in [C.ref_record(x) for x in libman.references]:
            if not C.ref_matches_identity(ref, spec):
                continue
            if any(C.ref_matches_identity(ref, w) for w in wanted_specs):
                continue
            libman.remove_library(ref['name'])
            report.add('removed', 'LIBRARY %s (не нужна в этом режиме)' % ref['name'])


# ---------------------------------------------------------------------------
# Шаг import
# ---------------------------------------------------------------------------


def check_device(proj, device, log):
    # type: (Any, Dict[str, Any], C.Log) -> None
    dev = C.find_device(proj)
    if dev is None:
        raise C.StepError('в проекте нет устройства; пересоздайте проект: cds.py import --clean')
    ident = dev.get_device_identification()
    have = (int(ident.type), C._text(ident.id), C._text(ident.version))
    want = (int(device['type']), C._text(device['id']), C._text(device['version']))
    if have != want:
        raise C.StepError(
            'устройство проекта %s не совпадает с config.json %s; пересоздайте проект: cds.py import --clean'
            % (have, want)
        )


def run(ctx, step):
    # type: (C.Context, Dict[str, Any]) -> Dict[str, Any]
    log = C.Log(step.get('log'))
    report = Report(log)
    try:
        repo_root = step['repo_root']
        with_tests = bool(step.get('with_tests'))
        tests_folder = step.get('tests_folder') or 'Tests'
        log.info('импорт: репозиторий %s, режим %s, тесты %s' % (repo_root, step.get('mode'), with_tests))
        wanted = scan_sources(repo_root, with_tests, tests_folder, log)
        mode_cfg = step.get('mode_config') or {}
        # библиотеки — до открытия проекта: если нужной версии нет, проект не меняется, а cds.py
        # по missing_libraries может собрать её из соседнего репозитория и повторить импорт
        resolved = resolve_libraries(mode_cfg.get('libraries') or [], step.get('library_repository'), log)
        proj, created = ctx.open_project(
            step['project'],
            create=True,
            device=step['device'],
            clean=bool(step.get('clean')),
            reopen=bool(step.get('reopen')),
            log=log,
        )
        if created:
            report.add('created', 'PROJECT %s' % step['project'])
        else:
            check_device(proj, step['device'], log)
        app = C.application(proj)
        syncer = Syncer(app, log, report)
        existing = syncer.existing_objects()
        wanted_names = dict((obj.name.lower(), obj) for obj, _ in wanted)
        syncer.remove_stale(wanted_names, existing)
        syncer.fix_name_case(wanted, existing)
        for obj, folder_path in wanted:
            syncer.sync_object(obj, folder_path, existing)
        wanted_paths = set()
        for _, folder_path in wanted:
            for i in range(1, len(folder_path) + 1):
                wanted_paths.add(tuple(p.lower() for p in folder_path[:i]))
        syncer.remove_empty_folders(wanted_paths)
        sync_tasks(app, mode_cfg.get('tasks') or [], log, report)
        sync_libraries(find_library_manager(app), resolved, step.get('other_libraries') or [], log, report)
        proj.save()
        log.info(
            'проект сохранён: создано %d, обновлено %d, удалено %d, перемещено %d, без изменений %d'
            % (len(report.created), len(report.updated), len(report.removed), len(report.moved), report.unchanged)
        )
        result = report.as_dict()
        result.update(
            {
                'ok': not log.errors,
                'project': step['project'],
                'mode': step.get('mode'),
                'with_tests': with_tests,
                'objects': len(wanted),
                'installed_libraries': installed_from_files(resolved),
                'warnings': log.warnings,
                'errors': log.errors,
            }
        )
        return result
    except C.StepError as exc:
        log.error('%s' % exc)
        raise
    except Exception as exc:
        log.error('исключение: %s' % exc)
        raise
    finally:
        if step.get('report'):
            data = report.as_dict()
            data.update({'warnings': log.warnings, 'errors': log.errors, 'project': step.get('project')})
            try:
                C.write_json(step['report'], data)
            except Exception:
                pass
        log.close()


if __name__ == '__main__':
    C.run_main('import')
