#!/usr/bin/env python3
"""Склейка раскладки src/ (и tests/) в стандартный ST — build/assembled/.

По файлу на объект верхнего уровня (<Имя>.st) и общий all.st. Порядок в all.st:
DUT, GVL, интерфейсы, функции, функциональные блоки (базовые раньше производных),
программы. Рядом пишется sourcemap.json — соответствие строк собранных файлов
строкам исходников (им пользуются run_rusty.py и run_iec_checker.py).

Варианты (--flavor): iec (по умолчанию, docs/LAYOUT.md), rusty (плюс замены для
компилятора RuSTy), iec-checker (понижение для разборщика iec_checker). Подробно —
tools/README.md.

Коды выхода: 0 — успех, 1 — ошибки раскладки или сборки, 2 — неверные аргументы.
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TextIO

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, "codesys"))
sys.path.insert(0, TOOLS_DIR)

import st_flavors as F  # noqa: E402
import stlayout as L  # noqa: E402

FLAVOR_IEC = "iec"
FLAVOR_RUSTY = "rusty"
FLAVOR_IEC_CHECKER = "iec-checker"
FLAVORS = (FLAVOR_IEC, FLAVOR_RUSTY, FLAVOR_IEC_CHECKER)

ALL_FILE = "all.st"
SOURCEMAP_FILE = "sourcemap.json"
COMPAT_UNIT = "__RustyCompat"

LAY_CROSS_DUPLICATE = "LAY006"
ASM_INHERITANCE_CYCLE = "ASM001"

GROUP_COMPAT = -1
GROUP_DUT = 0
GROUP_GVL = 1
GROUP_ITF = 2
GROUP_FUNCTION = 3
GROUP_FUNCTION_BLOCK = 4
GROUP_PROGRAM = 5

_POU_END = {
    L.POU_PROGRAM: "END_PROGRAM",
    L.POU_FUNCTION_BLOCK: "END_FUNCTION_BLOCK",
    L.POU_FUNCTION: "END_FUNCTION",
}


@dataclass
class Segment:
    """Диапазон строк собранного файла и его источник (None — сгенерированные строки)."""

    start: int
    count: int
    source: str | None
    source_start: int = 1

    def to_json(self) -> list[object]:
        return [self.start, self.count, self.source, self.source_start]


@dataclass
class Unit:
    """Собранный объект верхнего уровня."""

    name: str
    group: int
    text: str
    segments: list[Segment] = field(default_factory=list)

    @property
    def file_name(self) -> str:
        return self.name + ".st"


class UnitBuilder:
    def __init__(self) -> None:
        self._parts: list[str] = []
        self.segments: list[Segment] = []
        self._line = 1

    def add(self, text: str, source: str | None = None, source_start: int = 1) -> None:
        if not text:
            return
        if not text.endswith("\n"):
            text += "\n"
        count = text.count("\n")
        last = self.segments[-1] if self.segments else None
        if source is None and last is not None and last.source is None:
            last.count += count
        else:
            self.segments.append(Segment(self._line, count, source, source_start))
        self._parts.append(text)
        self._line += count

    def synthetic(self, text: str) -> None:
        self.add(text, None)

    def build(self, name: str, group: int) -> Unit:
        return Unit(name, group, "".join(self._parts), self.segments)


@dataclass
class AssembleResult:
    flavor: str
    units: list[Unit]
    all_unit: Unit
    issues: list[L.LayoutIssue]

    @property
    def errors(self) -> list[L.LayoutIssue]:
        return [i for i in self.issues if i.severity == "error"]


# ---------------------------------------------------------------------------
# Загрузка и порядок
# ---------------------------------------------------------------------------


def load_objects(root: str, subdirs: Sequence[str]) -> tuple[list[L.StObject], list[L.LayoutIssue]]:
    """Сканирует каталоги раскладки; имена объектов должны быть уникальны во всех."""
    objects: list[L.StObject] = []
    issues: list[L.LayoutIssue] = []
    seen: dict[str, L.StObject] = {}
    for subdir in subdirs:
        result = L.scan(root, subdir)
        issues.extend(result.issues)
        for obj in result.objects:
            key = obj.name.lower()
            if key in seen and seen[key].subdir != obj.subdir:
                issues.append(
                    L.LayoutIssue(
                        LAY_CROSS_DUPLICATE,
                        obj.main_path(),
                        1,
                        f"объект '{obj.name}' уже объявлен в {seen[key].main_path()}",
                    )
                )
                continue
            seen.setdefault(key, obj)
            objects.append(obj)
    return objects, issues


def object_group(obj: L.StObject) -> int:
    if obj.kind == L.KIND_DUT:
        return GROUP_DUT
    if obj.kind in (L.KIND_GVL, L.KIND_PVL):
        return GROUP_GVL
    if obj.kind == L.KIND_ITF:
        return GROUP_ITF
    if obj.pou_kind == L.POU_FUNCTION:
        return GROUP_FUNCTION
    if obj.pou_kind == L.POU_PROGRAM:
        return GROUP_PROGRAM
    return GROUP_FUNCTION_BLOCK


def _sort_key(obj: L.StObject) -> tuple[str, str]:
    return (obj.name.lower(), obj.name)


def order_objects(objects: Sequence[L.StObject]) -> tuple[list[L.StObject], list[L.LayoutIssue]]:
    """Группы в порядке all.st; внутри группы — базовые раньше производных, затем по имени."""
    issues: list[L.LayoutIssue] = []
    ordered: list[L.StObject] = []
    groups: dict[int, list[L.StObject]] = {}
    for obj in objects:
        groups.setdefault(object_group(obj), []).append(obj)
    for group in sorted(groups):
        members = groups[group]
        by_name = {o.name.lower(): o for o in members}
        deps = {o.name.lower(): {e.lower() for e in o.extends if e.lower() in by_name} for o in members}
        users: dict[str, set[str]] = {name: set() for name in by_name}
        for name, bases in deps.items():
            for base in bases:
                users[base].add(name)
        ready = [(_sort_key(by_name[n]), n) for n, bases in deps.items() if not bases]
        heapq.heapify(ready)
        done: set[str] = set()
        while ready:
            _, name = heapq.heappop(ready)
            done.add(name)
            ordered.append(by_name[name])
            for user in sorted(users[name]):
                deps[user].discard(name)
                if not deps[user] and user not in done:
                    heapq.heappush(ready, (_sort_key(by_name[user]), user))
        rest = sorted((by_name[n] for n in by_name if n not in done), key=_sort_key)
        for obj in rest:
            issues.append(
                L.LayoutIssue(
                    ASM_INHERITANCE_CYCLE,
                    obj.main_path(),
                    obj.header.line if obj.header else 1,
                    f"цикл наследования EXTENDS с участием {obj.name}",
                )
            )
            ordered.append(obj)
    return ordered, issues


# ---------------------------------------------------------------------------
# Сборка объектов
# ---------------------------------------------------------------------------


def _path(obj: L.StObject, member: str, suffix: str) -> str:
    return f"{obj.rel_dir()}/{member}{suffix}"


class _Assembler:
    def __init__(self, objects: Sequence[L.StObject], flavor: str, ctx: F.Context) -> None:
        self.flavor = flavor
        self.ctx = ctx
        self.by_name = {o.name.lower(): o for o in objects}
        self.tx: Callable[[str], str]
        if flavor == FLAVOR_RUSTY:
            self.tx = lambda text: F.rusty_text(text, ctx)
        elif flavor == FLAVOR_IEC_CHECKER:
            self.tx = lambda text: F.iec_checker_text(text, ctx)
        else:
            self.tx = lambda text: text

    def unit(self, obj: L.StObject) -> Unit:
        builder = UnitBuilder()
        if self.flavor == FLAVOR_IEC_CHECKER:
            base = self._project_base(obj)
            self.tx = lambda text: F.iec_checker_text(text, self.ctx, base)
        if obj.kind in (L.KIND_DUT, L.KIND_GVL, L.KIND_PVL):
            self._flat(builder, obj)
        elif obj.kind == L.KIND_ITF:
            self._interface(builder, obj)
        elif self.flavor == FLAVOR_IEC_CHECKER:
            self._pou_lowered(builder, obj)
        else:
            self._pou(builder, obj)
        return builder.build(obj.name, object_group(obj))

    # --- DUT, GVL ---------------------------------------------------------

    def _flat(self, b: UnitBuilder, obj: L.StObject) -> None:
        path = obj.main_path()
        if self.flavor == FLAVOR_IEC_CHECKER and obj.kind != L.KIND_DUT:
            b.synthetic(f"CONFIGURATION {obj.name}\n")
            b.add(self.tx(obj.decl), path)
            b.synthetic("END_CONFIGURATION\n")
        else:
            b.add(self.tx(obj.decl), path)

    # --- интерфейсы -------------------------------------------------------

    def _interface(self, b: UnitBuilder, obj: L.StObject) -> None:
        b.add(self.tx(obj.decl), obj.main_path())
        for method in obj.methods:
            b.add(self.tx(method.decl), _path(obj, method.name, L.SUFFIX_METHOD_DECL))
            b.synthetic("END_METHOD\n")
        for prop in obj.properties:
            if self.flavor == FLAVOR_IEC_CHECKER:
                ptype = _prop_type(prop)
                if prop.has_get:
                    b.synthetic(self.tx(f"METHOD {prop.name}__get : {ptype}\nEND_METHOD\n"))
                if prop.has_set:
                    b.synthetic(
                        self.tx(
                            f"METHOD {prop.name}__set\nVAR_INPUT\n    {prop.name} : {ptype};\nEND_VAR\nEND_METHOD\n"
                        )
                    )
                continue
            self._property(b, obj, prop)
        b.synthetic("END_INTERFACE\n")

    # --- POU (iec, rusty) -------------------------------------------------

    def _pou(self, b: UnitBuilder, obj: L.StObject) -> None:
        b.add(self.tx(obj.decl), obj.main_path())
        for method in obj.methods:
            b.add(self.tx(method.decl), _path(obj, method.name, L.SUFFIX_METHOD_DECL))
            if method.impl is not None:
                b.add(self.tx(method.impl), _path(obj, method.name, L.SUFFIX_METHOD_IMPL))
            b.synthetic("END_METHOD\n")
        for prop in obj.properties:
            self._property(b, obj, prop)
        if obj.impl is not None:
            b.add(self.tx(obj.impl), _path(obj, obj.name, L.SUFFIX_IMPL))
        b.synthetic(_POU_END.get(obj.pou_kind or "", "END_FUNCTION_BLOCK") + "\n")

    def _property(self, b: UnitBuilder, obj: L.StObject, prop: L.StProperty) -> None:
        accessors = (
            ("PROPERTY_GET", prop.has_get, prop.get_decl, prop.get_impl, "get"),
            ("PROPERTY_SET", prop.has_set, prop.set_decl, prop.set_impl, "set"),
        )
        for keyword, present, decl, impl, tag in accessors:
            if not present:
                continue
            header = F.edit_header(prop.decl, keyword=keyword, drop_modifiers=self.flavor == FLAVOR_RUSTY)
            b.add(self.tx(header), _path(obj, prop.name, L.SUFFIX_PROP_DECL))
            if decl is not None:
                b.add(self.tx(decl), _path(obj, prop.name, f".{tag}.decl.st"))
            if impl is not None:
                b.add(self.tx(impl), _path(obj, prop.name, f".{tag}.impl.st"))
            b.synthetic("END_PROPERTY\n")

    # --- POU (iec-checker) ------------------------------------------------

    def _pou_lowered(self, b: UnitBuilder, obj: L.StObject) -> None:
        header = F.edit_header(
            obj.decl,
            drop_modifiers=True,
            drop_extends=True,
            drop_implements=True,
            default_return_type="BOOL" if obj.pou_kind == L.POU_FUNCTION else None,
        )
        b.add(self.tx(header), obj.main_path())
        if obj.impl is not None:
            b.add(self.tx(obj.impl), _path(obj, obj.name, L.SUFFIX_IMPL))
        b.synthetic(_POU_END.get(obj.pou_kind or "", "END_FUNCTION_BLOCK") + "\n")
        own_vars = self._instance_vars(obj, set())
        for method in obj.methods:
            fname = f"{obj.name}__{method.name}"
            ret = method.header.return_type if method.header else None
            head = F.edit_header(
                method.decl,
                keyword="FUNCTION",
                name=fname,
                drop_modifiers=True,
                default_return_type="BOOL",
            )
            b.synthetic("\n")
            b.add(self.tx(head), _path(obj, method.name, L.SUFFIX_METHOD_DECL))
            extra = [f"    {method.name} : {ret};"] if ret else []
            self._injected_vars(b, obj, own_vars, [method.decl, method.impl or ""], extra)
            if method.impl is not None:
                b.add(self.tx(method.impl), _path(obj, method.name, L.SUFFIX_METHOD_IMPL))
            tail = f"{fname} := {method.name};\n" if ret else f"{fname} := TRUE;\n"
            b.synthetic(tail + "END_FUNCTION\n")
        for prop in obj.properties:
            ptype = _prop_type(prop)
            if prop.has_get:
                fname = f"{obj.name}__{prop.name}__get"
                b.synthetic(self.tx(f"\nFUNCTION {fname} : {ptype}\n"))
                if prop.get_decl is not None:
                    b.add(self.tx(prop.get_decl), _path(obj, prop.name, L.SUFFIX_GET_DECL))
                self._injected_vars(
                    b,
                    obj,
                    own_vars,
                    [prop.get_decl or "", prop.get_impl or ""],
                    [f"    {prop.name} : {ptype};"],
                )
                if prop.get_impl is not None:
                    b.add(self.tx(prop.get_impl), _path(obj, prop.name, L.SUFFIX_GET_IMPL))
                b.synthetic(f"{fname} := {prop.name};\nEND_FUNCTION\n")
            if prop.has_set:
                fname = f"{obj.name}__{prop.name}__set"
                b.synthetic(self.tx(f"\nFUNCTION {fname} : BOOL\nVAR_INPUT\n    {prop.name} : {ptype};\nEND_VAR\n"))
                if prop.set_decl is not None:
                    b.add(self.tx(prop.set_decl), _path(obj, prop.name, L.SUFFIX_SET_DECL))
                self._injected_vars(b, obj, own_vars, [prop.set_decl or "", prop.set_impl or ""], [], {prop.name})
                if prop.set_impl is not None:
                    b.add(self.tx(prop.set_impl), _path(obj, prop.name, L.SUFFIX_SET_IMPL))
                b.synthetic(f"{fname} := TRUE;\nEND_FUNCTION\n")

    def _project_base(self, obj: L.StObject) -> str | None:
        for name in obj.extends:
            base = self.by_name.get(name.lower())
            if base is not None and base.kind == L.KIND_POU:
                return base.name
        return None

    def _instance_vars(self, obj: L.StObject, seen: set[str]) -> list[tuple[list[str], str]]:
        """Переменные экземпляра POU и его базовых FB из проекта (базовые — первыми)."""
        seen.add(obj.name.lower())
        result: list[tuple[list[str], str]] = []
        for base_name in obj.extends:
            base = self.by_name.get(base_name.lower())
            if base is not None and base.kind == L.KIND_POU and base.name.lower() not in seen:
                result.extend(self._instance_vars(base, seen))
        result.extend(F.var_decls_source(obj.decl))
        return result

    def _injected_vars(
        self,
        b: UnitBuilder,
        obj: L.StObject,
        instance_vars: list[tuple[list[str], str]],
        texts: list[str],
        extra: list[str],
        exclude: set[str] | None = None,
    ) -> None:
        """VAR с копиями переменных экземпляра, которые упоминает член POU (приближение)."""
        used = F.referenced_names(*texts)
        local = set().union(*(F.declared_names(t) for t in texts)) if texts else set()
        skip = local | {n.lower() for n in (exclude or set())}
        lines: list[str] = []
        for names, rest in instance_vars:
            subset = [n for n in names if n.lower() in used and n.lower() not in skip]
            if subset:
                lines.append(f"    {', '.join(subset)} : {rest}")
        lines.extend(extra)
        if not lines:
            return
        text = f"VAR (* копии переменных {obj.name} — приближение для статанализа *)\n"
        b.synthetic(self.tx(text + "\n".join(lines) + "\nEND_VAR\n"))


def _prop_type(prop: L.StProperty) -> str:
    if prop.header is not None and prop.header.return_type:
        return prop.header.return_type
    return "BOOL"


def assemble_objects(
    objects: Sequence[L.StObject],
    flavor: str = FLAVOR_IEC,
    strip_namespaces: Sequence[str] = (),
) -> AssembleResult:
    """Собирает объекты (без записи на диск)."""
    if flavor not in FLAVORS:
        raise ValueError(f"неизвестный вариант сборки: {flavor}")
    ordered, issues = order_objects(objects)
    ctx = F.Context.from_objects(ordered, strip_namespaces)
    assembler = _Assembler(ordered, flavor, ctx)
    units = [assembler.unit(obj) for obj in ordered]
    if flavor == FLAVOR_RUSTY and ctx.used_itf_helper:
        compat = UnitBuilder()
        compat.synthetic(F.ITF_HELPER)
        units.insert(0, compat.build(COMPAT_UNIT, GROUP_COMPAT))
    return AssembleResult(flavor, units, _join_units(units), issues)


def _join_units(units: Sequence[Unit]) -> Unit:
    builder = UnitBuilder()
    for i, unit in enumerate(units):
        if i:
            builder.synthetic("\n")
        line = builder._line
        builder._parts.append(unit.text)
        for seg in unit.segments:
            builder.segments.append(Segment(line + seg.start - 1, seg.count, seg.source, seg.source_start))
        builder._line += unit.text.count("\n")
    return builder.build("all", GROUP_COMPAT)


# ---------------------------------------------------------------------------
# Запись и карта строк
# ---------------------------------------------------------------------------


def write_result(result: AssembleResult, out_dir: str) -> list[str]:
    """Пишет <Имя>.st, all.st, sourcemap.json; старые *.st в out_dir удаляются."""
    os.makedirs(out_dir, exist_ok=True)
    for entry in os.listdir(out_dir):
        full = os.path.join(out_dir, entry)
        if os.path.isfile(full) and (entry.endswith(".st") or entry == SOURCEMAP_FILE):
            os.remove(full)
    written: list[str] = []
    files: dict[str, list[list[object]]] = {}
    for unit in [*result.units, result.all_unit]:
        file_name = ALL_FILE if unit is result.all_unit else unit.file_name
        L.write_text(os.path.join(out_dir, file_name), unit.text)
        files[file_name] = [seg.to_json() for seg in unit.segments]
        written.append(file_name)
    # Компактный и детерминированный JSON: один сегмент — одна строка
    lines = ["{", '  "version": 1,', f'  "flavor": {json.dumps(result.flavor)},', '  "files": {']
    names = sorted(files)
    for i, name in enumerate(names):
        segments = ",\n".join(f"    {json.dumps(seg, ensure_ascii=False)}" for seg in files[name])
        comma = "," if i < len(names) - 1 else ""
        lines.append(f"   {json.dumps(name)}: [\n{segments}\n   ]{comma}")
    lines += ["  }", "}", ""]
    L.write_text(os.path.join(out_dir, SOURCEMAP_FILE), "\n".join(lines))
    return written


class SourceMap:
    """Карта строк собранных файлов на исходники раскладки."""

    def __init__(self, files: dict[str, list[list[object]]]) -> None:
        self.files = files

    @classmethod
    def load(cls, out_dir: str) -> SourceMap:
        path = os.path.join(out_dir, SOURCEMAP_FILE)
        if not os.path.isfile(path):
            return cls({})
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(data.get("files", {}))

    @classmethod
    def from_result(cls, result: AssembleResult) -> SourceMap:
        files = {u.file_name: [s.to_json() for s in u.segments] for u in result.units}
        files[ALL_FILE] = [s.to_json() for s in result.all_unit.segments]
        return cls(files)

    def lookup(self, file_name: str, line: int) -> tuple[str, int] | None:
        """(исходный файл, строка) или None для сгенерированных строк и чужих файлов."""
        for start, count, source, source_start in self.files.get(os.path.basename(file_name), []):
            assert isinstance(start, int) and isinstance(count, int)
            if start <= line < start + count:
                if source is None:
                    return None
                assert isinstance(source, str) and isinstance(source_start, int)
                return source, source_start + line - start
        return None

    def main_source(self, file_name: str) -> str | None:
        """Первый исходный файл собранного файла (для находок без строки, line = 0)."""
        for _, _, source, _ in self.files.get(os.path.basename(file_name), []):
            if isinstance(source, str):
                return source
        return None

    def is_synthetic(self, file_name: str, line: int) -> bool:
        for start, count, source, _ in self.files.get(os.path.basename(file_name), []):
            assert isinstance(start, int) and isinstance(count, int)
            if start <= line < start + count:
                return source is None
        return False


# ---------------------------------------------------------------------------
# Командная строка
# ---------------------------------------------------------------------------


def default_out(root: str, flavor: str) -> str:
    base = os.path.join(root, "build", "assembled")
    return base if flavor == FLAVOR_IEC else os.path.join(base, flavor)


def run(
    root: str,
    src: str = "src",
    tests: str | None = None,
    flavor: str = FLAVOR_IEC,
    out_dir: str | None = None,
    strip_namespaces: Sequence[str] = (),
    check_only: bool = False,
    stream: TextIO | None = None,
) -> tuple[int, AssembleResult]:
    """Сканирует, собирает и (если не check_only) пишет результат. Возвращает (код, результат)."""
    err = stream if stream is not None else sys.stderr
    subdirs = [src] + ([tests] if tests else [])
    objects, issues = load_objects(root, subdirs)
    result = assemble_objects(objects, flavor, strip_namespaces)
    result.issues[:0] = issues
    for issue in sorted(result.issues, key=lambda i: (i.path, i.line, i.code)):
        level = "ошибка" if issue.severity == "error" else "предупреждение"
        print(f"{issue.format()} [{level}]", file=err)
    if result.errors:
        print(
            f"assemble: {len(result.errors)} ошибок раскладки/сборки, результат не записан",
            file=err,
        )
        return 1, result
    if not check_only:
        write_result(result, out_dir or default_out(root, flavor))
    return 0, result


def _split_dir(root: str, path: str) -> tuple[str, str]:
    """Каталог раскладки -> (корень, имя подкаталога) для stlayout.scan."""
    full = path if os.path.isabs(path) else os.path.join(root, path)
    full = os.path.normpath(full)
    return os.path.dirname(full), os.path.basename(full)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="assemble.py",
        description="Склейка раскладки ST (docs/LAYOUT.md) в build/assembled/.",
    )
    parser.add_argument("--root", default=REPO_ROOT, help="корень репозитория (по умолчанию — рядом с tools/)")
    parser.add_argument("--src", default="src", help="каталог исходников (от --root), по умолчанию src")
    parser.add_argument("--tests", action="store_true", help="добавить объекты из tests/")
    parser.add_argument("--tests-dir", default="tests", help="каталог тестов, по умолчанию tests")
    parser.add_argument("--out", help="каталог результата (по умолчанию build/assembled[/<flavor>])")
    parser.add_argument("--flavor", choices=FLAVORS, default=FLAVOR_IEC, help="вариант сборки")
    parser.add_argument(
        "--strip-namespace",
        action="append",
        default=[],
        metavar="NS",
        help="убрать префикс пространства имён библиотеки (например CfUnit.); можно повторять",
    )
    parser.add_argument("--check-only", action="store_true", help="только проверить раскладку, ничего не писать")
    parser.add_argument("-q", "--quiet", action="store_true", help="без итогового сообщения")
    return parser


def configure_output() -> None:
    """Вывод в UTF-8 и при перенаправлении в файл или канал (Windows по умолчанию — cp1251)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    configure_output()
    args = build_parser().parse_args(argv)
    root = os.path.abspath(args.root)
    src_root, src = _split_dir(root, args.src)
    tests: str | None = None
    if args.tests:
        tests_root, tests = _split_dir(root, args.tests_dir)
        if tests_root != src_root:
            print("assemble: --src и --tests-dir должны лежать в одном каталоге", file=sys.stderr)
            return 2
    out_dir = os.path.abspath(args.out) if args.out else default_out(root, args.flavor)
    code, result = run(
        src_root,
        src,
        tests,
        args.flavor,
        out_dir,
        args.strip_namespace,
        args.check_only,
    )
    if code == 0 and not args.quiet:
        action = "проверено" if args.check_only else f"записано в {out_dir}"
        print(f"assemble: {len(result.units)} объектов ({args.flavor}), {action}")
    return code


if __name__ == "__main__":
    sys.exit(main())
