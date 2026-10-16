#!/usr/bin/env python3
"""Проверка собранного ST компилятором RuSTy: plc --check (без компоновки).

Шаги: сборка варианта rusty (src/ + tests/) в build/assembled/rusty/, затем
plc --check <файлы> -i <stdlib> -i <прокладки>. Файлы из tools/check/rusty_exclude.txt
не проверяются (у каждого — причина). Диагностики пересчитываются на строки исходников
по sourcemap.json; журнал — build/rusty.log, сводка — build/rusty.json.

Компилятор: --plc, переменная RUSTY_PLC, PATH (plc), ~/.local/plc-tools/rusty/plc[.exe].
Объявления стандартной библиотеки (*.st): --stdlib, RUSTY_STDLIB_INCLUDE или каталоги рядом
с компилятором (stdlib/stdlib/include, stdlib/include, include).
--optional: нет компилятора или stdlib — предупреждение и код 0 (необязательный шаг CI).

Коды выхода: 0 — проверка прошла (или пропущена с --optional), 1 — ошибки компиляции,
раскладки или нет инструмента, 2 — неверные аргументы или файл исключений.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass

CHECK_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(CHECK_DIR)
REPO_ROOT = os.path.dirname(TOOLS_DIR)
sys.path.insert(0, TOOLS_DIR)

import assemble  # noqa: E402

DEFAULT_EXCLUDE = os.path.join(CHECK_DIR, "rusty_exclude.txt")
DEFAULT_SHIMS = os.path.join(CHECK_DIR, "rusty_shims")
DEFAULT_NAMESPACES = ("coUnit", "CfUnit")
KNOWN_PLC = os.path.join("~", ".local", "plc-tools", "rusty", "plc")
STDLIB_CANDIDATES = (
    os.path.join("stdlib", "stdlib", "include"),
    os.path.join("stdlib", "include"),
    "include",
)

_DIAG_RE = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+):\{[^}]*\}: "
    r"(?P<severity>error|warning|info|note)\[(?P<code>E\d+)\]: (?P<message>.*)$"
)


class ToolMissing(Exception):
    pass


class ExcludeError(Exception):
    pass


@dataclass
class Diagnostic:
    severity: str
    code: str
    message: str
    file: str
    line: int
    col: int
    source: str | None = None
    source_line: int | None = None

    def format(self) -> str:
        where = f"{self.source}:{self.source_line}" if self.source else f"{self.file}:{self.line}"
        built = f" (собрано: {self.file}:{self.line})" if self.source else ""
        return f"{where}:{self.col}: {self.severity}[{self.code}] {self.message}{built}"


def _exe_variants(path: str) -> list[str]:
    return [path, path + ".exe"] if os.name == "nt" else [path]


def find_compiler(
    explicit: str | None = None,
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> str:
    """Путь к plc: аргумент, RUSTY_PLC, PATH, ~/.local/plc-tools/rusty/plc."""
    env = os.environ if env is None else env
    for candidate in (explicit, env.get("RUSTY_PLC")):
        if candidate:
            if os.path.isfile(candidate):
                return candidate
            raise ToolMissing(f"компилятор RuSTy не найден: {candidate}")
    found = which("plc")
    if found:
        return found
    for candidate in _exe_variants(os.path.expanduser(KNOWN_PLC)):
        if os.path.isfile(candidate):
            return candidate
    raise ToolMissing("компилятор RuSTy (plc) не найден: задайте RUSTY_PLC или добавьте plc в PATH")


def find_stdlib(plc: str, explicit: str | None = None, env: Mapping[str, str] | None = None) -> list[str]:
    """Файлы объявлений стандартной библиотеки RuSTy (*.st), отсортированные."""
    env = os.environ if env is None else env
    directory = explicit or env.get("RUSTY_STDLIB_INCLUDE")
    if directory:
        if not os.path.isdir(directory):
            raise ToolMissing(f"нет каталога stdlib RuSTy: {directory}")
    else:
        base = os.path.dirname(os.path.abspath(plc))
        for candidate in STDLIB_CANDIDATES:
            full = os.path.join(base, candidate)
            if os.path.isdir(full):
                directory = full
                break
    if not directory:
        raise ToolMissing("не найдены объявления stdlib RuSTy: задайте RUSTY_STDLIB_INCLUDE")
    files = sorted(os.path.join(directory, n) for n in os.listdir(directory) if n.endswith(".st"))
    if not files:
        raise ToolMissing(f"в {directory} нет файлов *.st")
    return files


def read_exclude(path: str) -> dict[str, str]:
    """Файл исключений: '<Имя>.st  # причина' на строку; '#' в начале — комментарий."""
    result: dict[str, str] = {}
    if not os.path.isfile(path):
        return result
    with open(path, encoding="utf-8") as fh:
        for number, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            name, _, reason = line.partition("#")
            name = name.strip()
            reason = reason.strip()
            if not reason:
                raise ExcludeError(f"{path}:{number}: у исключения '{name}' нет причины (# причина)")
            if not name.endswith(".st"):
                name += ".st"
            result[name] = reason
    return result


def build_command(plc: str, files: Sequence[str], stdlib: Sequence[str], shims: Sequence[str]) -> list[str]:
    cmd = [plc, "--check", *files]
    for include in [*stdlib, *shims]:
        cmd += ["-i", include]
    cmd += ["--error-format", "clang"]
    return cmd


def parse_diagnostics(output: str) -> list[Diagnostic]:
    result: list[Diagnostic] = []
    for line in output.splitlines():
        match = _DIAG_RE.match(line.strip())
        if not match:
            continue
        path = match.group("path")
        if path.startswith("\\\\?\\"):
            path = path[4:]
        result.append(
            Diagnostic(
                severity=match.group("severity"),
                code=match.group("code"),
                message=match.group("message"),
                file=os.path.basename(path.replace("\\", "/")),
                line=int(match.group("line")),
                col=int(match.group("col")),
            )
        )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_rusty.py", description="Проверка ST компилятором RuSTy.")
    parser.add_argument("--root", default=REPO_ROOT, help="корень репозитория")
    parser.add_argument("--src", default="src", help="каталог исходников (от --root)")
    parser.add_argument("--tests-dir", default="tests", help="каталог тестов (от --root)")
    parser.add_argument("--no-tests", action="store_true", help="не проверять tests/")
    parser.add_argument("--out", help="каталог сборки (по умолчанию build/assembled/rusty)")
    parser.add_argument("--plc", help="путь к компилятору plc")
    parser.add_argument("--stdlib", help="каталог объявлений stdlib RuSTy (*.st)")
    parser.add_argument("--exclude-file", default=DEFAULT_EXCLUDE, help="файл исключений")
    parser.add_argument("--shims", default=DEFAULT_SHIMS, help="каталог прокладок *.st")
    parser.add_argument(
        "--strip-namespace",
        action="append",
        default=None,
        metavar="NS",
        help=f"пространства имён библиотек для удаления (по умолчанию {', '.join(DEFAULT_NAMESPACES)})",
    )
    parser.add_argument("--log", help="журнал (по умолчанию build/rusty.log)")
    parser.add_argument("--json", dest="json_out", help="сводка JSON (по умолчанию build/rusty.json)")
    parser.add_argument("--optional", action="store_true", help="нет компилятора — предупреждение и код 0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    assemble.configure_output()
    args = build_parser().parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        plc = find_compiler(args.plc)
        stdlib = find_stdlib(plc, args.stdlib)
    except ToolMissing as exc:
        if args.optional:
            print(f"run_rusty: ПРЕДУПРЕЖДЕНИЕ: {exc}; проверка RuSTy пропущена (--optional)")
            return 0
        print(f"run_rusty: {exc}", file=sys.stderr)
        return 1
    try:
        excluded = read_exclude(args.exclude_file)
    except ExcludeError as exc:
        print(f"run_rusty: {exc}", file=sys.stderr)
        return 2
    out_dir = os.path.abspath(args.out) if args.out else assemble.default_out(root, assemble.FLAVOR_RUSTY)
    namespaces = args.strip_namespace if args.strip_namespace is not None else list(DEFAULT_NAMESPACES)
    code, result = assemble.run(
        root,
        args.src,
        None if args.no_tests else args.tests_dir,
        assemble.FLAVOR_RUSTY,
        out_dir,
        namespaces,
    )
    if code != 0:
        return 1
    produced = sorted(u.file_name for u in result.units)
    for name in sorted(excluded):
        if name not in produced:
            print(f"run_rusty: предупреждение: исключение {name} не соответствует ни одному файлу")
    files = [os.path.join(out_dir, n) for n in produced if n not in excluded]
    shims = (
        sorted(os.path.join(args.shims, n) for n in os.listdir(args.shims) if n.endswith(".st"))
        if os.path.isdir(args.shims)
        else []
    )
    cmd = build_command(plc, files, stdlib, shims)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    output = (proc.stdout or "") + (proc.stderr or "")
    sourcemap = assemble.SourceMap.from_result(result)
    diagnostics = parse_diagnostics(output)
    for diag in diagnostics:
        mapped = sourcemap.lookup(diag.file, diag.line)
        if mapped:
            diag.source, diag.source_line = mapped
    build_dir = os.path.join(root, "build")
    log_path = os.path.abspath(args.log) if args.log else os.path.join(build_dir, "rusty.log")
    json_path = os.path.abspath(args.json_out) if args.json_out else os.path.join(build_dir, "rusty.json")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(" ".join(cmd) + "\n\n" + output)
    errors = [d for d in diagnostics if d.severity == "error"]
    summary = {
        "version": 1,
        "returncode": proc.returncode,
        "files": [os.path.basename(f) for f in files],
        "excluded": excluded,
        "diagnostics": [asdict(d) for d in diagnostics],
        "errors": len(errors),
        "warnings": sum(1 for d in diagnostics if d.severity == "warning"),
    }
    with open(json_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    for diag in diagnostics:
        print(diag.format())
    ok = proc.returncode == 0
    status = "без ошибок" if ok else f"ошибок {len(errors)} (код plc {proc.returncode})"
    print(f"run_rusty: проверено файлов {len(files)}, исключено {len(excluded)}, {status}; журнал {log_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
