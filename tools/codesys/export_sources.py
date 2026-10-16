# -*- coding: utf-8 -*-
"""Экспорт ST-объектов проекта CODESYS в раскладку src/ (и tests/) — скрипт CODESYS Scripting (IronPython 2.7).

Запуск — только через tools/codesys/cds.py (python tools/codesys/cds.py export [--tests] [--to DIR]).

Экспортируются объекты приложения: DUT, GVL, Persistent Variables, интерфейсы (методы, свойства)
и POU на ST (методы, свойства с аксессорами). Библиотеки, дерево устройств, конфигурация задач,
визуализации, действия (ACTION) и POU на графических языках не экспортируются — о последних
пишется предупреждение. Объекты из папки Tests (config.json: tests_folder) уходят в tests/,
остальные — в src/; папки проекта становятся подкаталогами категорий (docs/LAYOUT.md).

Запись — stlayout.write_objects (единственный писатель раскладки): нормализация текста (LF, без
хвостовых пробелов, один перевод строки в конце), детерминированный набор файлов; файлы *.st
объектов, которых больше нет в проекте, удаляются (clean=True). Без --tests каталог tests/ не
трогается.

Правила обратного отображения (зеркальны импорту):
- объявление аксессора свойства POU, равное объявлению по умолчанию 'VAR / END_VAR', файла
  <P>.get.decl.st не даёт; тело аксессора пишется всегда (<P>.get.impl.st, возможно пустой);
- у аксессоров интерфейса есть только объявление: <P>.get.decl.st (обычно пустой);
- у метода ABSTRACT с пустым телом файла <M>.method.impl.st нет.
"""
from __future__ import absolute_import, print_function, unicode_literals

import cds_common as C
import stlayout as L

MYPY = False
if MYPY:  # pragma: no cover
    from typing import Any, Dict, List, Optional, Tuple  # noqa: F401

_KIND_TO_LAYOUT = {
    C.K_DUT: L.KIND_DUT,
    C.K_GVL: L.KIND_GVL,
    C.K_PVL: L.KIND_PVL,
    C.K_ITF: L.KIND_ITF,
    C.K_POU: L.KIND_POU,
}
_POU_KIND_OF_KEYWORD = {
    'PROGRAM': L.POU_PROGRAM,
    'FUNCTION_BLOCK': L.POU_FUNCTION_BLOCK,
    'FUNCTION': L.POU_FUNCTION,
}


def _accessors(prop):
    # type: (Any) -> Dict[str, Any]
    return dict((C.obj_name(a), a) for a in C.children(prop) if C.kind_of(a) == C.K_ACCESSOR)


def export_property(prop_obj, owner, is_itf, log):
    # type: (Any, str, bool, C.Log) -> L.StProperty
    name = C.obj_name(prop_obj)
    prop = L.StProperty(name, C.decl_text(prop_obj) or '')
    for acc_name, acc in sorted(_accessors(prop_obj).items()):
        if acc_name not in (C.ACCESSOR_GET, C.ACCESSOR_SET):
            log.warn('%s.%s: неизвестный аксессор %s пропущен' % (owner, name, acc_name))
            continue
        decl = C.decl_text(acc)
        impl = C.impl_text(acc)
        if is_itf:
            decl = decl if decl is not None else ''
            impl = None
        else:
            if decl is not None and C.is_default_accessor_decl(decl):
                decl = None
            if impl is None:
                impl = ''
        if acc_name == C.ACCESSOR_GET:
            prop.get_decl, prop.get_impl = decl, impl
        else:
            prop.set_decl, prop.set_impl = decl, impl
    prop.header = L.parse_header(prop.decl)
    return prop


def export_members(cur, st_obj, log):
    # type: (Any, L.StObject, C.Log) -> None
    is_itf = st_obj.kind == L.KIND_ITF
    for child in C.children(cur):
        kind = C.kind_of(child)
        name = C.obj_name(child)
        if kind == C.K_METHOD:
            decl = C.decl_text(child) or ''
            impl = None if is_itf else C.impl_text(child)
            method = L.StMethod(name, decl, impl)
            method.header = L.parse_header(decl)
            if method.impl is not None and not L.normalize_text(method.impl) and method.is_abstract:
                method.impl = None
            if not is_itf and not C.has_impl(child):
                log.warn('%s.%s: метод не на ST — тело не экспортировано' % (st_obj.name, name))
            st_obj.methods.append(method)
        elif kind == C.K_PROPERTY:
            st_obj.properties.append(export_property(child, st_obj.name, is_itf, log))
        else:
            log.warn('%s.%s: объект вида %s не входит в раскладку — не экспортирован' % (st_obj.name, name, kind))
    st_obj.sorted_members()


def collect(app, tests_folder, log):
    # type: (Any, str, C.Log) -> Tuple[List[L.StObject], List[L.StObject]]
    """Объекты приложения: (для src/, для tests/)."""
    src = []  # type: List[L.StObject]
    tests = []  # type: List[L.StObject]

    def walk(parent, path):
        # type: (Any, List[str]) -> None
        for obj in C.children(parent):
            kind = C.kind_of(obj)
            name = C.obj_name(obj)
            if kind == C.K_FOLDER:
                walk(obj, path + [name])
                continue
            if kind in (C.K_LIBMAN, C.K_TASK_CONFIG):
                continue
            if kind not in _KIND_TO_LAYOUT:
                log.warn('%s: объект вида %s (%s) не входит в раскладку — не экспортирован'
                         % ('/'.join(path + [name]), kind, C._text(obj.type)))
                continue
            in_tests = bool(path) and path[0].lower() == tests_folder.lower()
            folder = path[1:] if in_tests else list(path)
            decl = C.decl_text(obj)
            if decl is None:
                log.warn('%s: нет текстового объявления — не экспортирован' % name)
                continue
            st_obj = L.StObject(_KIND_TO_LAYOUT[kind], name, decl, folder=folder,
                                subdir='tests' if in_tests else 'src')
            st_obj.header = L.parse_header(decl)
            if kind == C.K_POU:
                if not C.has_impl(obj):
                    log.warn('%s: POU не на ST (графический язык) — не экспортирован, ручной шаг' % name)
                    continue
                st_obj.impl = C.impl_text(obj)
                keyword = st_obj.header.keyword if st_obj.header is not None else None
                st_obj.pou_kind = _POU_KIND_OF_KEYWORD.get(keyword)
            if kind in (C.K_POU, C.K_ITF):
                export_members(obj, st_obj, log)
            (tests if in_tests else src).append(st_obj)

    walk(app, [])
    return src, tests


def run(ctx, step):
    # type: (C.Context, Dict[str, Any]) -> Dict[str, Any]
    log = C.Log(step.get('log'))
    try:
        out_root = step['out_root']
        with_tests = bool(step.get('with_tests'))
        tests_folder = step.get('tests_folder') or 'Tests'
        proj, _ = ctx.open_project(step['project'], create=False, reopen=bool(step.get('reopen')), log=log)
        app = C.application(proj)
        src, tests = collect(app, tests_folder, log)
        log.info('объектов: src %d, tests %d' % (len(src), len(tests)))
        if not src:
            # защита от затирания src/ экспортом пустого или чужого проекта
            raise C.StepError('в проекте %s нет объектов раскладки — экспорт отменён' % step['project'])
        written = L.write_objects(src, out_root, 'src', clean=True)
        if with_tests:
            written += L.write_objects(tests, out_root, 'tests', clean=True)
        elif tests:
            log.warn('в проекте есть папка %s (%d объектов), экспорт без --tests: tests/ не изменён'
                     % (tests_folder, len(tests)))
        for rel in sorted(written):
            log.info('записан %s' % rel)
        result = {
            'ok': True,
            'out_root': out_root,
            'project': step['project'],
            'with_tests': with_tests,
            'objects_src': len(src),
            'objects_tests': len(tests),
            'files': len(written),
            'warnings': log.warnings,
        }
        if step.get('report'):
            C.write_json(step['report'], result)
        return result
    except Exception as exc:
        log.error('%s' % exc)
        raise
    finally:
        log.close()


if __name__ == '__main__':
    C.run_main('export')
