#!/usr/bin/env python3
"""Статанализ iec_checker для plc-iiot-stack: обёртка над tools/check/run_iec_checker.py (шаблон).

Зачем обёртка. iec_checker 0.4 не разбирает несколько конструкций CODESYS, без которых ПЛК-часть стека
не обходится, а run_iec_checker.py не позволяет обосновать ParserError. Править шаблон (tools/check,
tools/assemble.py, tools/st_flavors.py) в проекте нельзя, поэтому обёртка:

1. собирает вариант iec-checker тем же tools/assemble.py, что и run_iec_checker.py;
2. дополнительно понижает собранный текст, не меняя номеров строк (только для анализа):
   - длины строк и границы массивов из именованных констант (STRING[GVL_Const.MQTT_TOPIC_LEN],
     ARRAY[1..GVL_IiotMap.POINT_COUNT]) заменяет их числовыми значениями из исходников;
   - многострочное начальное значение массива понижение шаблона убирает, но оставляет ';' отдельной
     строкой (GVL_IiotMap: POINT_CFG, RULE_CFG, ALARM_CFG): ';' возвращается в объявление;
   - AND_THEN и OR_ELSE (расширение CODESYS) заменяет на AND и OR: порядок вычисления для анализа
     iec_checker не важен;
   - обращение к полю элемента массива a[i].b (и a[i].b.c) сокращает до a[i]: в грамматике
     iec_checker 0.4 нет поля после индекса, а сам он поля структур использованием не считает;
3. запускает iec_checker и классифицирует находки по tools/check/iec_checker_allow.toml, как
   run_iec_checker.py (те же отчёты build/iec_checker.json и build/iec_checker.md); находку
   UnusedVariable, для которой в теле POU или в его методах есть обращение к переменной, отмечает
   обоснованной с местом обращения (iec_checker 0.4 не видит обращений из методов, к полям и через ADR);
4. ParserError (и UnknownError разборщика) принимает только там, где он описан в
   tools_project/iec_checker_parser_gaps.toml (файл и регулярное выражение по тексту строки);
   любая другая необоснованная находка — ошибка;
5. запись о пробеле, которой больше не соответствует ни одна находка, — ошибка (список актуален);
   обоснование из iec_checker_allow.toml, которое ни разу не использовано, — ошибка (с тестами).

Коды выхода: 0 — все находки обоснованы; 1 — нет (или устаревшие записи); 2 — неверные настройки;
3 — нет iec_checker (с --optional — предупреждение и 0). Итог обёртки — build/iec_checker_gate.json.
Разбор находок — docs/STATIC_ANALYSIS.md.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent
for extra in (REPO_ROOT / "tools" / "check", REPO_ROOT / "tools", REPO_ROOT / "tools" / "codesys"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import assemble  # noqa: E402
import run_iec_checker as R  # noqa: E402

DEFAULT_GAPS = PROJECT_DIR / "iec_checker_parser_gaps.toml"
GAP_IDS = (*R.PARSER_IDS, "UnknownError")
EXIT_OK, EXIT_FAIL, EXIT_CONFIG, EXIT_TOOL = 0, 1, 2, 3
NL = "\n"

# Целочисленная константа в объявлении: NAME : DINT := 121;  (имя — UPPER_SNAKE_CASE по правилам проекта)
_CONST_DECL = re.compile(
    r"^\s*([A-Z][A-Z0-9_]*)\s*:\s*(?:U?S?INT|U?D?INT|U?L?INT|BYTE|WORD|DWORD|LWORD)\s*:=\s*(-?\d+)\s*;"
)
# Скобки, в которых iec_checker 0.4 ждёт только числа: длина строки и границы массива
_BRACKETS = re.compile(r"\b(W?STRING|ARRAY)\[([^\]]*)\]")
_NAME = re.compile(r"\b(?:[A-Za-z_]\w*\.)?[A-Z][A-Z0-9_]*\b")
# Объявление массива без ';' и без начального значения (его убрало понижение шаблона)
_ARRAY_NO_SEMI = re.compile(r"^(\s*\w+\s*:\s*ARRAY\[[^\]]*\]\s+OF\s+[\w.]+(?:\[[^\]]*\])?)\s*(//.*)?$")
_LONE_SEMI = re.compile(r"^\s*;\s*$")
_SHORT_CIRCUIT = re.compile(r"\b(AND_THEN|OR_ELSE)\b")
_FIELD_AFTER_INDEX = re.compile(r"\]((?:\.[A-Za-z_]\w*)+)")


class GapError(Exception):
    """Неверный файл пробелов разборщика."""


@dataclass
class Gap:
    file: str
    match: re.Pattern[str]
    reason: str
    used: int = 0


@dataclass
class Lowering:
    constants: int = 0  # подставлено числовых значений
    semicolons: int = 0  # возвращено ';'
    short_circuit: int = 0  # AND_THEN/OR_ELSE -> AND/OR
    fields: int = 0  # a[i].b -> a[i]


@dataclass
class GateResult:
    errors: list[dict[str, Any]] = field(default_factory=list)  # необоснованные находки
    known: list[dict[str, Any]] = field(default_factory=list)  # находки разборщика из списка пробелов
    stale_gaps: list[Gap] = field(default_factory=list)
    unused_allow: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.errors or self.stale_gaps or self.unused_allow)


def load_gaps(path: Path) -> list[Gap]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise GapError(f"{path}: {exc}") from exc
    gaps: list[Gap] = []
    for n, item in enumerate(data.get("gap", []), 1):
        file, match, reason = item.get("file"), item.get("match"), item.get("reason")
        if not (isinstance(file, str) and isinstance(match, str) and isinstance(reason, str) and reason.strip()):
            raise GapError(f"{path}: запись {n}: нужны file, match и непустой reason")
        try:
            pattern = re.compile(match)
        except re.error as exc:
            raise GapError(f"{path}: запись {n}: match: {exc}") from exc
        gaps.append(Gap(file, pattern, reason))
    return gaps


def collect_constants(files: Iterable[Path]) -> dict[str, int]:
    """Целочисленные константы исходников: 'GVL_Const.NAME' (из GVL) и 'NAME' (если значение однозначно)."""
    qualified: dict[str, int] = {}
    bare: dict[str, set[int]] = {}
    for path in files:
        stem = path.name.split(".", 1)[0]
        is_gvl = path.name.endswith(".gvl.st")
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _CONST_DECL.match(line)
            if not m:
                continue
            name, value = m.group(1), int(m.group(2))
            bare.setdefault(name, set()).add(value)
            if is_gvl:
                qualified[f"{stem}.{name}"] = value
    table = dict(qualified)
    table.update({name: next(iter(values)) for name, values in bare.items() if len(values) == 1})
    return table


def _eval_int(expr: str) -> int | None:
    """Значение выражения из целых чисел и + - * (границы массива вида 0..N - 1), иначе None."""
    try:
        node = ast.parse(expr.strip(), mode="eval").body
    except SyntaxError:
        return None

    def ev(n: ast.AST) -> int | None:
        if isinstance(n, ast.Constant) and type(n.value) is int:
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            v = ev(n.operand)
            return None if v is None else -v
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult)):
            a, b = ev(n.left), ev(n.right)
            if a is None or b is None:
                return None
            return a + b if isinstance(n.op, ast.Add) else a - b if isinstance(n.op, ast.Sub) else a * b
        return None

    return ev(node)


def lower_line(line: str, constants: dict[str, int], stats: Lowering) -> str:
    """Одна строка собранного текста после понижения обёртки (число строк не меняется)."""

    def bracket(m: re.Match[str]) -> str:
        def name(n: re.Match[str]) -> str:
            value = constants.get(n.group(0))
            if value is None:
                return n.group(0)
            stats.constants += 1
            return str(value)

        inner = _NAME.sub(name, m.group(2))
        dims = []
        for dim in inner.split(","):
            bounds = dim.split("..")
            values = [_eval_int(b) for b in bounds]
            dims.append("..".join(b.strip() if v is None else str(v) for b, v in zip(bounds, values, strict=True)))
        return f"{m.group(1)}[{', '.join(dims)}]"

    out = _BRACKETS.sub(bracket, line)
    code, sep, comment = out.partition("//")
    code, n = _SHORT_CIRCUIT.subn(lambda m: "AND" if m.group(1) == "AND_THEN" else "OR", code)
    stats.short_circuit += n
    code, n = _FIELD_AFTER_INDEX.subn("]", code)
    stats.fields += n
    return code + sep + comment


def lower_text(text: str, constants: dict[str, int], stats: Lowering) -> str:
    """Собранный файл после понижения обёртки: число строк то же, что и у собранного шаблоном."""
    lines: list[str] = []
    pending_semi = False  # объявлению вернули ';' — ждём одинокую ';' от убранного начального значения
    for raw in text.split(NL):
        line = lower_line(raw, constants, stats)
        m = _ARRAY_NO_SEMI.match(line)
        if m and ":=" not in line:
            line = f"{m.group(1)};" + (f" {m.group(2)}" if m.group(2) else "")
            pending_semi = True
        elif pending_semi and _LONE_SEMI.match(line):
            stats.semicolons += 1
            line = ""
            pending_semi = False
        elif pending_semi and line.strip():
            # ';' нет не из-за убранного начального значения — понижение шаблона изменилось, разобраться
            raise ValueError(f"неожиданное объявление массива без ';' перед строкой: {line.strip()}")
        lines.append(line)
    if pending_semi:
        raise ValueError("объявление массива без ';' в конце файла")
    return NL.join(lines)


def lower_dir(out_dir: Path, names: Iterable[str], constants: dict[str, int]) -> Lowering:
    stats = Lowering()
    for name in names:
        path = out_dir / name
        try:
            text = lower_text(path.read_text(encoding="utf-8"), constants, stats)
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from exc
        path.write_text(text, encoding="utf-8", newline=NL)
    return stats


_COMMENT = re.compile(r"//[^\n]*|\(\*.*?\*\)", re.S)
_ST_STRING = re.compile(r"'(?:\$.|[^'$\n])*'")


def code_text(path: Path) -> str:
    """Текст ST без комментариев и строковых литералов; переводы строк сохраняются (номера строк те же)."""
    text = path.read_text(encoding="utf-8")
    text = _COMMENT.sub(lambda m: NL * m.group(0).count(NL), text)
    return _ST_STRING.sub("''", text)


def usage_files(root: Path, source: str) -> list[Path]:
    """Где искать обращения к переменной из объявления source.

    Объявление метода — только тело этого метода; объявление POU — тело и все методы и свойства POU.
    """
    path = root / source
    if path.name.endswith(".method.decl.st"):
        return [path.with_name(path.name.replace(".method.decl.st", ".method.impl.st"))]
    if path.name.endswith(".decl.st"):
        return [p for p in sorted(path.parent.glob("*.st")) if p != path]
    return []


def confirm_usage(findings: Iterable[R.Finding], root: Path) -> int:
    """UnusedVariable, у которой в коде POU есть обращение к переменной, — ложное срабатывание.

    iec_checker 0.4 не считает использованием обращения из методов (сборка выносит методы в отдельные
    функции), к полям структур и к методам и полям ФБ (stCmd.xAck, fbParser.Parse(...)), а также ADR() и ^.
    Такая находка получает статус allowed с местом первого обращения; остальные остаются ошибками.
    """
    confirmed = 0
    for f in findings:
        if f.status != "error" or f.id != "UnusedVariable" or not f.source:
            continue
        var = f.msg.rsplit(":", 1)[-1].strip()
        if not re.fullmatch(r"\w+", var):
            continue
        pattern = re.compile(rf"\b{re.escape(var)}\b", re.IGNORECASE)
        for path in usage_files(root, f.source):
            if not path.is_file():
                continue
            text = code_text(path)
            m = pattern.search(text)
            if m:
                where = f"{path.relative_to(root).as_posix()}:{text.count(NL, 0, m.start()) + 1}"
                f.status = "allowed"
                f.reason = (
                    f"Ложное срабатывание, проверено обёрткой: обращение в {where} (iec_checker 0.4 не учитывает "
                    "обращения из методов, к полям и методам ФБ и структур, ADR() и ^)"
                )
                confirmed += 1
                break
    return confirmed


def source_line(root: Path, source: str | None, line: int | None) -> str:
    if not source or not line:
        return ""
    try:
        lines = (root / source).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    return lines[line - 1] if 0 < line <= len(lines) else ""


def evaluate(report: dict[str, Any], gaps: list[Gap], root: Path, require_all_allow: bool) -> GateResult:
    """Разбор отчёта: находки разборщика из списка пробелов допустимы, прочие необоснованные — нет.

    require_all_allow = False — проверялся только src/: записи о пробелах в tests/ и неиспользованные
    обоснования не проверяются.
    """
    if not require_all_allow:
        gaps = [g for g in gaps if not g.file.startswith("tests/")]
    result = GateResult()
    for finding in report.get("findings", []):
        if finding.get("status") != "error":
            continue
        if finding.get("id") in GAP_IDS:
            text = source_line(root, finding.get("source"), finding.get("source_line"))
            gap = next((g for g in gaps if g.file == finding.get("source") and g.match.search(text)), None)
            if gap is not None:
                gap.used += 1
                result.known.append({**finding, "reason": gap.reason, "line_text": text.strip()})
                continue
        result.errors.append(finding)
    result.stale_gaps = [g for g in gaps if not g.used]
    if require_all_allow:
        result.unused_allow = list(report.get("unused_allow", []))
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="iec_checker_gate.py", description="iec_checker для plc-iiot-stack (обёртка).")
    p.add_argument("--root", default=str(REPO_ROOT), help="корень репозитория")
    p.add_argument("--no-tests", action="store_true", help="только src/ (без проверки неиспользованных обоснований)")
    p.add_argument("--gaps", default=str(DEFAULT_GAPS), help="файл пробелов разборщика (TOML)")
    p.add_argument("--allow", default=R.DEFAULT_ALLOW, help="файл обоснований TOML")
    p.add_argument("--binary", default=None, help="путь к iec_checker")
    p.add_argument("--docker", default=None, metavar="IMAGE", help="Docker-образ iec_checker")
    p.add_argument("--optional", action="store_true", help="нет инструмента — предупреждение и код 0")
    return p


def run_checker(root: Path, args: argparse.Namespace, rules: list[R.AllowRule]) -> tuple[int, dict[str, Any]]:
    """Сборка, понижение обёртки, iec_checker, классификация; отчёты как у run_iec_checker.py."""
    binary: str | None = None
    if args.docker:
        if shutil.which("docker") is None:
            raise R.ToolMissing("docker не найден в PATH")
    else:
        binary = R.find_binary(args.binary)
    out_dir = Path(assemble.default_out(str(root), assemble.FLAVOR_IEC_CHECKER))
    tests_dir = None if args.no_tests else "tests"
    code, result = assemble.run(str(root), "src", tests_dir, assemble.FLAVOR_IEC_CHECKER, str(out_dir), [])
    if code != 0:
        return EXIT_FAIL, {}
    names = sorted(u.file_name for u in result.units)
    sources = sorted((root / "src").rglob("*.st"))
    if tests_dir:
        sources += sorted((root / tests_dir).rglob("*.st"))
    stats = lower_dir(out_dir, names, collect_constants(sources))
    sourcemap = assemble.SourceMap.from_result(result)
    findings: list[R.Finding] = []
    for name in names:
        cmd = R.build_command(str(out_dir / name), binary, args.docker)
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        findings.extend(R.parse_output((proc.stdout or "") + "\n" + (proc.stderr or ""), name))
    R.classify(findings, sourcemap, rules)
    confirmed = confirm_usage(findings, root)
    findings.sort(key=lambda f: (f.status != "error", f.source or f.file, f.source_line or f.line, f.id))
    tool = f"docker {args.docker}" if args.docker else str(binary)
    summary = {s: sum(1 for f in findings if f.status == s) for s in ("error", "allowed", "artifact")}
    report = {
        "version": 1,
        "tool": tool,
        "files": names,
        "lowering": asdict(stats),
        "unused_variable_confirmed": confirmed,
        "findings": [asdict(f) for f in findings],
        "summary": summary,
        "unused_allow": [asdict(r) for r in rules if not r.used],
    }
    build = root / "build"
    build.mkdir(parents=True, exist_ok=True)
    with open(build / "iec_checker.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(build / "iec_checker.md", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(R.markdown_report(findings, rules, tool))
    print(
        f"iec_checker_gate: файлов {len(names)}; понижение обёртки: констант {stats.constants}, "
        f"';' {stats.semicolons}, AND_THEN/OR_ELSE {stats.short_circuit}, a[i].b {stats.fields}; "
        f"UnusedVariable с найденным обращением {confirmed}"
    )
    return EXIT_OK, report


def main(argv: Sequence[str] | None = None) -> int:
    assemble.configure_output()
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    try:
        gaps = load_gaps(Path(args.gaps))
        rules = R.load_allow(args.allow)
    except (GapError, R.AllowError) as exc:
        print(f"iec_checker_gate: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    try:
        code, report = run_checker(root, args, rules)
    except R.ToolMissing as exc:
        if args.optional:
            print(f"iec_checker_gate: ПРЕДУПРЕЖДЕНИЕ: {exc}; статанализ пропущен (--optional)")
            return EXIT_OK
        print(f"iec_checker_gate: {exc}", file=sys.stderr)
        return EXIT_TOOL
    if code != EXIT_OK:
        return code
    result = evaluate(report, gaps, root, require_all_allow=not args.no_tests)
    for finding in result.known:
        print(
            f"iec_checker_gate: известный пробел разборщика: {finding.get('source')}:{finding.get('source_line')}: "
            f"{finding.get('line_text')}"
        )
    for finding in result.errors:
        where = f"{finding.get('source') or finding.get('file')}:{finding.get('source_line') or finding.get('line')}"
        print(f"iec_checker_gate: НЕОБОСНОВАННО: {where}: {finding.get('id')}: {finding.get('msg')}", file=sys.stderr)
    for gap in result.stale_gaps:
        print(f"iec_checker_gate: устаревшая запись о пробеле: {gap.file} ({gap.match.pattern})", file=sys.stderr)
    for rule in result.unused_allow:
        print(f"iec_checker_gate: неиспользованное обоснование: {rule.get('id')} / {rule.get('file')}", file=sys.stderr)
    summary = {
        "version": 1,
        "ok": result.ok,
        "errors": len(result.errors),
        "known_parser_gaps": [
            {"source": f.get("source"), "line": f.get("source_line"), "text": f.get("line_text"), "reason": f["reason"]}
            for f in result.known
        ],
        "stale_gaps": [g.file for g in result.stale_gaps],
        "unused_allow": result.unused_allow,
        "lowering": report.get("lowering", {}),
        "run_iec_checker": report.get("summary", {}),
    }
    out = root / "build" / "iec_checker_gate.json"
    os.makedirs(out.parent, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = report.get("summary", {})
    print(
        f"iec_checker_gate: {'пройдено' if result.ok else 'НЕ пройдено'}; необоснованных {len(result.errors)}, "
        f"известных пробелов разборщика {len(result.known)}, обоснованных {counts.get('allowed', 0)}, "
        f"артефактов сборки {counts.get('artifact', 0)}"
    )
    return EXIT_OK if result.ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
