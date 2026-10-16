#!/usr/bin/env python3
"""Статанализ собранного ST утилитой iec_checker (github.com/jubnzv/iec-checker).

Шаги: сборка варианта iec-checker в build/assembled/iec-checker/, запуск iec_checker
по каждому файлу (так у каждой находки известен файл), пересчёт строк на исходники
по sourcemap.json, сверка с файлом обоснований tools/check/iec_checker_allow.toml.
Отчёты: build/iec_checker.json и build/iec_checker.md.

Статусы находок:
- error — не обоснована: код выхода 1. ParserError/LexingError — всегда error;
- allowed — есть запись в файле обоснований (id + шаблон файла + причина);
- artifact — находка на строке, которую создала сборка (копии переменных ФБ в
  функциях-методах и т. п.), а не на строке исходника; кода выхода не меняет.

Запуск: локальный бинарник (--binary, переменная IEC_CHECKER, PATH,
~/.local/plc-tools/iec-checker/) или Docker-образ (--docker jubnzv1/iec-checker:nightly).
Коды выхода: 0 — нет необоснованных находок, 1 — есть (или нет инструмента/ошибка
сборки), 2 — неверные аргументы или файл обоснований.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass

CHECK_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(CHECK_DIR)
REPO_ROOT = os.path.dirname(TOOLS_DIR)
sys.path.insert(0, TOOLS_DIR)

import assemble  # noqa: E402

DEFAULT_ALLOW = os.path.join(CHECK_DIR, "iec_checker_allow.toml")
BINARY_NAMES = ("iec_checker", "iec_checker_Linux_x86_64", "iec_checker_Windows_x86_64.exe")
KNOWN_DIR = os.path.join("~", ".local", "plc-tools", "iec-checker")
PARSER_IDS = ("ParserError", "LexingError")
DOCKER_WORKDIR = "/work"


class ToolMissing(Exception):
    pass


class AllowError(Exception):
    pass


@dataclass
class AllowRule:
    id: str
    file: str
    reason: str
    match: str = ""
    used: int = 0

    def matches(self, finding: Finding) -> bool:
        if not fnmatch.fnmatchcase(finding.id, self.id):
            return False
        targets = [finding.file]
        if finding.source:
            targets.append(finding.source)
        if not any(fnmatch.fnmatchcase(t, self.file) for t in targets):
            return False
        return not self.match or re.search(self.match, finding.msg) is not None


@dataclass
class Finding:
    id: str
    msg: str
    file: str
    line: int
    column: int
    source: str | None = None
    source_line: int | None = None
    status: str = "error"
    reason: str = ""

    def location(self) -> str:
        if self.source:
            return f"{self.source}:{self.source_line}"
        return f"{self.file}:{self.line}"


def load_allow(path: str) -> list[AllowRule]:
    """Файл обоснований: таблицы [[allow]] с ключами id, file, reason и необязательным match."""
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise AllowError(f"{path}: {exc}") from exc
    rules: list[AllowRule] = []
    for number, entry in enumerate(data.get("allow", []), 1):
        missing = [key for key in ("id", "file", "reason") if not str(entry.get(key, "")).strip()]
        if missing:
            raise AllowError(f"{path}: запись [[allow]] №{number}: нет {', '.join(missing)}")
        match = str(entry.get("match", ""))
        try:
            re.compile(match)
        except re.error as exc:
            raise AllowError(f"{path}: запись №{number}: неверное регулярное выражение match: {exc}") from exc
        rules.append(AllowRule(str(entry["id"]), str(entry["file"]), str(entry["reason"]).strip(), match))
    return rules


def _exe(path: str) -> bool:
    return os.path.isfile(path)


def find_binary(
    explicit: str | None = None,
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> str:
    """Путь к iec_checker: аргумент, IEC_CHECKER, PATH, ~/.local/plc-tools/iec-checker/."""
    env = os.environ if env is None else env
    for candidate in (explicit, env.get("IEC_CHECKER")):
        if candidate:
            if _exe(candidate):
                return candidate
            raise ToolMissing(f"iec_checker не найден: {candidate}")
    for name in BINARY_NAMES:
        found = which(name)
        if found:
            return found
    known = os.path.expanduser(KNOWN_DIR)
    for name in BINARY_NAMES:
        if _exe(os.path.join(known, name)):
            return os.path.join(known, name)
    raise ToolMissing("iec_checker не найден: задайте IEC_CHECKER, добавьте его в PATH или используйте --docker")


def build_command(
    file_path: str, binary: str | None = None, docker_image: str | None = None, docker: str = "docker"
) -> list[str]:
    """Команда проверки одного файла: локальный бинарник или docker run."""
    if docker_image:
        directory = os.path.dirname(os.path.abspath(file_path))
        return [
            docker,
            "run",
            "--rm",
            "-v",
            f"{directory}:{DOCKER_WORKDIR}",
            "-w",
            DOCKER_WORKDIR,
            docker_image,
            "-o",
            "json",
            os.path.basename(file_path),
        ]
    if not binary:
        raise ValueError("нужен binary или docker_image")
    return [binary, "-o", "json", file_path]


def parse_output(output: str, file_name: str) -> list[Finding]:
    """Разбирает вывод `iec_checker -o json`: один или несколько JSON-массивов по строкам."""
    findings: list[Finding] = []
    parsed_any = False
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("["):
            continue
        try:
            items = json.loads(line)
        except json.JSONDecodeError:
            continue
        parsed_any = True
        for item in items:
            findings.append(
                Finding(
                    id=str(item.get("id", "")),
                    msg=str(item.get("msg", "")),
                    file=file_name,
                    line=int(item.get("linenr", 0) or 0),
                    column=int(item.get("column", 0) or 0),
                )
            )
    if not parsed_any:
        tail = " ".join(output.split())[:300]
        findings.append(Finding("ToolError", f"нет JSON в выводе iec_checker: {tail}", file_name, 0, 0))
    return findings


def classify(findings: list[Finding], sourcemap: assemble.SourceMap, rules: list[AllowRule]) -> None:
    for finding in findings:
        if finding.line > 0:
            mapped = sourcemap.lookup(finding.file, finding.line)
            if mapped:
                finding.source, finding.source_line = mapped
        else:
            # находка на весь файл (например, PLCOPEN-CP9): относим к объявлению объекта
            finding.source = sourcemap.main_source(finding.file)
            finding.source_line = 0 if finding.source else None
        if finding.id in PARSER_IDS or finding.id == "ToolError":
            finding.status = "error"
            continue
        rule = next((r for r in rules if r.matches(finding)), None)
        if rule is not None:
            rule.used += 1
            finding.status = "allowed"
            finding.reason = rule.reason
        elif finding.line > 0 and sourcemap.is_synthetic(finding.file, finding.line):
            finding.status = "artifact"
            finding.reason = "строка создана сборкой iec-checker, а не взята из исходника"
        else:
            finding.status = "error"


def markdown_report(findings: Sequence[Finding], rules: Sequence[AllowRule], tool: str) -> str:
    counts = {s: sum(1 for f in findings if f.status == s) for s in ("error", "allowed", "artifact")}
    lines = [
        "# Отчёт iec_checker",
        "",
        f"Инструмент: `{tool}`. Обоснования: `tools/check/iec_checker_allow.toml`, "
        "разбор находок — `docs/STATIC_ANALYSIS.md`.",
        "",
        "| Статус | Число |",
        "|---|---|",
        f"| необоснованные (error) | {counts['error']} |",
        f"| обоснованные (allowed) | {counts['allowed']} |",
        f"| артефакты сборки (artifact) | {counts['artifact']} |",
        "",
    ]
    for status, title in (("error", "Необоснованные находки"), ("allowed", "Обоснованные находки")):
        selected = [f for f in findings if f.status == status]
        if not selected:
            continue
        lines += [f"## {title}", "", "| Правило | Место | Сообщение | Обоснование |", "|---|---|---|---|"]
        for f in selected:
            msg = f.msg.replace("|", "\\|")
            lines.append(f"| {f.id} | `{f.location()}` | {msg} | {f.reason.replace('|', '/')} |")
        lines.append("")
    unused = [r for r in rules if not r.used]
    if unused:
        lines += ["## Неиспользованные обоснования", ""]
        lines += [f"- `{r.id}` / `{r.file}`: {r.reason}" for r in unused]
        lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_iec_checker.py", description="Статанализ ST утилитой iec_checker.")
    parser.add_argument("--root", default=REPO_ROOT, help="корень репозитория")
    parser.add_argument("--src", default="src", help="каталог исходников (от --root)")
    parser.add_argument("--tests", action="store_true", help="проверять и tests/")
    parser.add_argument("--tests-dir", default="tests", help="каталог тестов (от --root)")
    parser.add_argument("--out", help="каталог сборки (по умолчанию build/assembled/iec-checker)")
    parser.add_argument("--binary", help="путь к iec_checker")
    parser.add_argument("--docker", metavar="IMAGE", help="Docker-образ, например jubnzv1/iec-checker:nightly")
    parser.add_argument("--allow", default=DEFAULT_ALLOW, help="файл обоснований TOML")
    parser.add_argument("--strip-namespace", action="append", default=[], metavar="NS")
    parser.add_argument("--json", dest="json_out", help="отчёт JSON (по умолчанию build/iec_checker.json)")
    parser.add_argument("--md", dest="md_out", help="отчёт Markdown (по умолчанию build/iec_checker.md)")
    parser.add_argument("--optional", action="store_true", help="нет инструмента — предупреждение и код 0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    assemble.configure_output()
    args = build_parser().parse_args(argv)
    root = os.path.abspath(args.root)
    binary: str | None = None
    try:
        if args.docker:
            if shutil.which("docker") is None:
                raise ToolMissing("docker не найден в PATH")
        else:
            binary = find_binary(args.binary)
    except ToolMissing as exc:
        if args.optional:
            print(f"run_iec_checker: ПРЕДУПРЕЖДЕНИЕ: {exc}; статанализ пропущен (--optional)")
            return 0
        print(f"run_iec_checker: {exc}", file=sys.stderr)
        return 1
    try:
        rules = load_allow(args.allow)
    except AllowError as exc:
        print(f"run_iec_checker: {exc}", file=sys.stderr)
        return 2
    out_dir = os.path.abspath(args.out) if args.out else assemble.default_out(root, assemble.FLAVOR_IEC_CHECKER)
    code, result = assemble.run(
        root,
        args.src,
        args.tests_dir if args.tests else None,
        assemble.FLAVOR_IEC_CHECKER,
        out_dir,
        args.strip_namespace,
    )
    if code != 0:
        return 1
    sourcemap = assemble.SourceMap.from_result(result)
    findings: list[Finding] = []
    for name in sorted(u.file_name for u in result.units):
        cmd = build_command(os.path.join(out_dir, name), binary, args.docker)
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        findings.extend(parse_output((proc.stdout or "") + "\n" + (proc.stderr or ""), name))
    classify(findings, sourcemap, rules)
    findings.sort(key=lambda f: (f.status != "error", f.source or f.file, f.source_line or f.line, f.id))
    tool = f"docker {args.docker}" if args.docker else str(binary)
    build_dir = os.path.join(root, "build")
    json_path = os.path.abspath(args.json_out) if args.json_out else os.path.join(build_dir, "iec_checker.json")
    md_path = os.path.abspath(args.md_out) if args.md_out else os.path.join(build_dir, "iec_checker.md")
    for path in (json_path, md_path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    summary = {s: sum(1 for f in findings if f.status == s) for s in ("error", "allowed", "artifact")}
    payload = {
        "version": 1,
        "tool": tool,
        "files": sorted(u.file_name for u in result.units),
        "findings": [asdict(f) for f in findings],
        "summary": summary,
        "unused_allow": [asdict(r) for r in rules if not r.used],
    }
    with open(json_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(md_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(markdown_report(findings, rules, tool))
    for finding in findings:
        if finding.status == "error":
            print(f"{finding.location()}: {finding.id}: {finding.msg} (собрано: {finding.file}:{finding.line})")
    skipped = [] if args.tests else [args.tests_dir.rstrip("/") + "/"]
    for rule in rules:
        if not rule.used and not rule.file.startswith(tuple(skipped)):
            print(f"run_iec_checker: предупреждение: обоснование {rule.id} / {rule.file} не использовано")
    print(
        f"run_iec_checker: файлов {len(result.units)}; необоснованных {summary['error']}, "
        f"обоснованных {summary['allowed']}, артефактов сборки {summary['artifact']}; отчёт {md_path}"
    )
    return 1 if summary["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
