#!/usr/bin/env python3
"""Линтер исходников ST по правилам CONTRIBUTING.md и docs/LAYOUT.md.

Проверяет каталоги раскладки (по умолчанию src/ и tests/): замечания раскладки
(LAYxxx из stlayout) и правила STL001-STL012 (таблица — tools/README.md).
Настройки — tools/check/st_lint.toml. Подавление на строке:
    // lint:allow STL008 причина
(комментарий на той же строке или отдельной строкой над ней; причина обязательна).

Коды выхода: 0 — нет ошибок, 1 — есть ошибки (или предупреждения при --strict),
2 — ошибка настроек или аргументов.
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import json
import os
import re
import sys
import tomllib
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from typing import Any

CHECK_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(CHECK_DIR)
REPO_ROOT = os.path.dirname(TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, "codesys"))

import stlayout as L  # noqa: E402

DEFAULT_CONFIG_PATH = os.path.join(CHECK_DIR, "st_lint.toml")

RULES: dict[str, str] = {
    "STL001": "нет заголовка-комментария POU (назначение, автор, версия, документ)",
    "STL002": "табуляция вместо пробелов",
    "STL003": "строка длиннее предела",
    "STL004": "TODO/FIXME без номера issue, нужно TODO(#12)",
    "STL005": "не-ASCII символ в идентификаторе или вне комментариев и строк",
    "STL006": "имя POU/DUT/GVL/интерфейса/метода/свойства не по правилам именования",
    "STL007": "префикс переменной не соответствует типу; константа не UPPER_SNAKE_CASE",
    "STL008": "магическое число в логике",
    "STL009": "файл не нормализован (кодировка, BOM, CRLF, перевод строки, хвостовые пробелы)",
    "STL010": 'не-ASCII символ в литерале STRING, нужен WSTRING "..."',
    "STL011": "отсчёт времени счётом циклов (эвристика)",
    "STL012": "неверное подавление lint:allow",
}

SEVERITIES = ("error", "warning", "off")
# Префиксы массивов (STL007): match — 'a' или 'a' + префикс типа элемента (astCfg — массив ST_*,
# axFlag — массив BOOL; если тип элемента правилу неизвестен — 'a' + любой известный префикс);
# any — 'a' или 'a' + любой известный префикс; off — только 'a' и заглавная буква (aValues)
ARRAY_PREFIX_MODES = ("match", "any", "off")

DEFAULT_CONFIG: dict[str, Any] = {
    "lint": {"paths": ["src", "tests"], "exclude": [], "max_line_length": 120},
    "severity": dict.fromkeys(RULES, "error") | {"STL011": "warning"},
    "rules": {
        "STL001": {
            "keywords": ["назначение", "автор", "версия", "документ"],
            "require_docs_link": True,
            "exclude": [],
        },
        "STL006": {
            "program": ["PRG_"],
            "function_block": ["FB_"],
            "function": ["F_"],
            "struct": ["ST_"],
            "enum": ["E_"],
            "union": ["U_"],
            "alias": [],
            "interface": ["I_"],
            "gvl": ["GVL_"],
            "pvl": ["PVL_", "GVL_"],
            "member_pattern": "^[A-Z][A-Za-z0-9]*$",
            "member_exceptions": ["FB_init", "FB_exit", "FB_reinit"],
            "exclude": [],
        },
        "STL007": {
            "allow_names": [],
            "constant_pattern": "^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$",
            "array_element_prefixes": "match",
            "type_prefixes": {
                "BOOL": "x",
                "BYTE": "b",
                "WORD": "w",
                "DWORD": "dw",
                "LWORD": "lw",
                "SINT": "si",
                "USINT": "usi",
                "INT": "i",
                "UINT": "ui",
                "DINT": "di",
                "UDINT": "udi",
                "LINT": "li",
                "ULINT": "uli",
                "REAL": "r",
                "LREAL": "lr",
                "STRING": "s",
                "WSTRING": "ws",
                "TIME": "t",
                "LTIME": "lt",
                "DATE": "d",
                "TOD": "tod",
                "TIME_OF_DAY": "tod",
                "DT": "dt",
                "DATE_AND_TIME": "dt",
            },
            "type_name_prefixes": {"E_": "e", "ST_": "st", "U_": "u", "FB_": "fb", "I_": "itf"},
            "fb_types": ["TON", "TOF", "TP", "R_TRIG", "F_TRIG", "CTU", "CTD", "CTUD", "RS", "SR"],
            "exclude": [],
        },
        "STL008": {
            "allowed_values": [0, 1, 2],
            "exempt_objects": ["GVL_Const"],
            "exclude": ["tests/*"],
        },
        "STL011": {
            "name_pattern": "(?i)(cycle|cyc|scan|tick)",
            "time_name_pattern": "(?i)(time|delay|timeout|_ms$|_s$|sec)",
            "exclude": [],
        },
    },
}


class ConfigError(Exception):
    pass


@dataclass
class Finding:
    rule: str
    path: str
    line: int
    col: int
    message: str
    severity: str = "error"

    def format(self) -> str:
        level = {"error": "ошибка", "warning": "предупреждение"}.get(self.severity, self.severity)
        return f"{self.path}:{self.line}:{self.col}: {self.rule} [{level}] {self.message}"


# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | None) -> dict[str, Any]:
    """Настройки по умолчанию, дополненные файлом TOML (если он есть)."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    if path is None:
        return config
    if not os.path.isfile(path):
        raise ConfigError(f"нет файла настроек: {path}")
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    _check_keys(data, DEFAULT_CONFIG, path, "")
    config = _merge(config, data)
    for rule, severity in config["severity"].items():
        if rule not in RULES:
            raise ConfigError(f"{path}: неизвестное правило в [severity]: {rule}")
        if severity not in SEVERITIES:
            raise ConfigError(f"{path}: {rule}: уровень должен быть одним из {SEVERITIES}")
    for rule in config["rules"]:
        if rule not in RULES:
            raise ConfigError(f"{path}: неизвестное правило в [rules]: {rule}")
    mode = config["rules"]["STL007"].get("array_element_prefixes")
    if mode not in ARRAY_PREFIX_MODES:
        raise ConfigError(f"{path}: rules.STL007.array_element_prefixes: одно из {ARRAY_PREFIX_MODES}")
    return config


# Таблицы, ключи которых задаёт проект (имена правил и типов), а не набор настроек
_FREE_TABLES = ("severity", "type_prefixes", "type_name_prefixes")


def _check_keys(data: dict[str, Any], defaults: dict[str, Any], path: str, where: str) -> None:
    """Каждый ключ файла настроек известен, значение — того же вида, что значение по умолчанию."""
    table = where.rsplit(".", 1)[-1]
    for key, value in data.items():
        name = f"{where}.{key}" if where else key
        if where == "rules":
            if key not in RULES:
                raise ConfigError(f"{path}: неизвестное правило в [rules]: {key}")
            if not isinstance(value, dict):
                raise ConfigError(f"{path}: [{name}] должна быть таблицей")
            _check_keys(value, defaults.get(key, {"exclude": []}), path, name)
            continue
        if table in _FREE_TABLES:
            if not isinstance(value, str):
                raise ConfigError(f"{path}: {name}: нужна строка")
            continue
        if key not in defaults:
            raise ConfigError(f"{path}: неизвестный ключ настроек: {name}")
        default = defaults[key]
        if isinstance(default, dict):
            if not isinstance(value, dict):
                raise ConfigError(f"{path}: [{name}] должна быть таблицей")
            _check_keys(value, default, path, name)
        elif isinstance(default, bool) or isinstance(value, bool):
            if not (isinstance(default, bool) and isinstance(value, bool)):
                raise ConfigError(f"{path}: {name}: нужно true или false")
        elif not isinstance(value, type(default)):
            raise ConfigError(f"{path}: {name}: нужно {type(default).__name__}, задано {type(value).__name__}")


def _matches(path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


# ---------------------------------------------------------------------------
# Линтер
# ---------------------------------------------------------------------------

_SUPPRESS_RE = re.compile(r"lint:allow\b(?P<body>[^\n]*)")
_SUPPRESS_BODY_RE = re.compile(r"\s*(?P<rules>[A-Z]+\d{3}(?:\s*,\s*[A-Z]+\d{3})*)\s*(?P<reason>.*)$")
_TODO_RE = re.compile(r"\b(TODO|FIXME)\b(?!\(#\d+\))")
# Секции констант (STL007, UPPER_SNAKE_CASE): VAR, VAR_GLOBAL (и VAR_STAT, VAR_EXTERNAL) с CONSTANT.
# VAR_IN_OUT CONSTANT и VAR_INPUT CONSTANT — параметры только для чтения: для них префиксы по типу
_CONSTANT_BLOCKS = ("VAR", "VAR_GLOBAL", "VAR_STAT", "VAR_EXTERNAL")
_COMPARISON_OPS = ("<", ">", "<=", ">=", "=", "<>")


class Linter:
    def __init__(self, root: str, config: dict[str, Any]) -> None:
        self.root = root
        self.config = config
        self.findings: list[Finding] = []
        self.suppressions: dict[str, dict[int, set[str]]] = {}
        self.files_checked = 0

    # --- общее --------------------------------------------------------------

    def severity(self, rule: str) -> str:
        if rule.startswith("LAY"):
            return "error"
        return str(self.config["severity"].get(rule, "error"))

    def rule_cfg(self, rule: str) -> dict[str, Any]:
        return dict(self.config["rules"].get(rule, {}))

    def report(self, rule: str, path: str, line: int, col: int, message: str, severity: str | None = None) -> None:
        level = severity or self.severity(rule)
        if level == "off":
            return
        if not rule.startswith("LAY") and _matches(path, self.rule_cfg(rule).get("exclude", [])):
            return
        self.findings.append(Finding(rule, path, line, col, message, level))

    def run(self, paths: Sequence[str]) -> list[Finding]:
        exclude = self.config["lint"].get("exclude", [])
        for subdir in paths:
            for rel in self._layout_files(subdir):
                if not _matches(rel, exclude):
                    self.check_file(rel)
            result = L.scan(self.root, subdir)
            for issue in result.issues:
                if not _matches(issue.path, exclude):
                    self.report(issue.code, issue.path, issue.line, 1, issue.message, issue.severity)
            for obj in result.objects:
                if not _matches(obj.main_path(), exclude):
                    self.check_object(obj)
        self._apply_suppressions()
        self.findings.sort(key=lambda f: (f.path, f.line, f.col, f.rule, f.message))
        return self.findings

    def _layout_files(self, subdir: str) -> Iterator[str]:
        base = os.path.join(self.root, subdir)
        if not os.path.isdir(base):
            return
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for name in sorted(filenames):
                if name.endswith(".st") and not name.startswith("."):
                    full = os.path.join(dirpath, name)
                    yield os.path.relpath(full, self.root).replace(os.sep, "/")

    def _apply_suppressions(self) -> None:
        kept: list[Finding] = []
        for finding in self.findings:
            allowed = self.suppressions.get(finding.path, {}).get(finding.line, set())
            if finding.rule not in allowed:
                kept.append(finding)
        self.findings = kept

    # --- правила уровня файла ----------------------------------------------

    def check_file(self, rel: str) -> None:
        self.files_checked += 1
        path = os.path.join(self.root, *rel.split("/"))
        with open(path, "rb") as fh:
            data = fh.read()
        try:
            raw = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            self.report("STL009", rel, 1, 1, f"файл не в кодировке UTF-8 ({exc.reason})")
            return
        self._check_normalized(rel, raw)
        text = raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        limit = int(self.config["lint"].get("max_line_length", 120))
        for number, content in enumerate(lines, 1):
            if "\t" in content:
                self.report("STL002", rel, number, content.index("\t") + 1, "табуляция: отступы — 4 пробела")
            if len(content) > limit:
                self.report("STL003", rel, number, limit + 1, f"длина строки {len(content)} > {limit}")
        tokens = L.tokenize(text)
        self._collect_suppressions(rel, tokens, lines)
        for tok in tokens:
            if tok.kind == L.TK_COMMENT:
                for match in _TODO_RE.finditer(tok.text):
                    line, col = _offset_position(tok, match.start())
                    self.report(
                        "STL004", rel, line, col, f"{match.group(1)} без номера issue: пишите {match.group(1)}(#N)"
                    )
            elif tok.kind in (L.TK_IDENT, L.TK_OTHER) and not tok.text.isascii():
                what = "идентификатор" if tok.kind == L.TK_IDENT else "символ"
                self.report(
                    "STL005", rel, tok.line, tok.col, f"не-ASCII {what} '{tok.text}': идентификаторы — только ASCII"
                )
            elif tok.kind == L.TK_STRING and not tok.text.isascii():
                self.report(
                    "STL010", rel, tok.line, tok.col, "не-ASCII в STRING '...': для кириллицы — WSTRING \"...\""
                )

    def _check_normalized(self, rel: str, raw: str) -> None:
        if raw.startswith("\ufeff"):
            self.report("STL009", rel, 1, 1, "BOM в начале файла (нужен UTF-8 без BOM)")
        if "\r" in raw:
            line = raw[: raw.index("\r")].count("\n") + 1
            self.report("STL009", rel, line, 1, "переводы строк CRLF/CR (нужен LF)")
        text = raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
        if not text.strip():
            return
        if not text.endswith("\n"):
            self.report("STL009", rel, text.count("\n") + 1, 1, "нет перевода строки в конце файла")
        elif text.endswith("\n\n"):
            self.report("STL009", rel, len(text.rstrip("\n").split("\n")) + 1, 1, "пустые строки в конце файла")
        for number, content in enumerate(text.split("\n"), 1):
            if content != content.rstrip(" \t"):
                self.report("STL009", rel, number, len(content.rstrip(" \t")) + 1, "хвостовые пробелы")

    def _collect_suppressions(self, rel: str, tokens: Sequence[L.Token], lines: Sequence[str]) -> None:
        table = self.suppressions.setdefault(rel, {})
        for tok in tokens:
            if tok.kind != L.TK_COMMENT:
                continue
            for match in _SUPPRESS_RE.finditer(tok.text):
                line, col = _offset_position(tok, match.start())
                body = match.group("body")
                body = re.sub(r"\*\)\s*$", "", body)
                parsed = _SUPPRESS_BODY_RE.match(body)
                if parsed is None:
                    self.report("STL012", rel, line, col, "lint:allow: укажите правило и причину")
                    continue
                rules = [r.strip() for r in parsed.group("rules").split(",")]
                reason = parsed.group("reason").strip()
                unknown = [r for r in rules if r not in RULES]
                if unknown:
                    self.report("STL012", rel, line, col, f"lint:allow: неизвестное правило {', '.join(unknown)}")
                    continue
                if not reason:
                    self.report("STL012", rel, line, col, "lint:allow без причины — подавление не действует")
                    continue
                # строка с комментарием; если комментарий стоит в строке один — и следующая за ним строка
                targets = {line}
                prefix = lines[tok.line - 1][: tok.col - 1] if 0 < tok.line <= len(lines) else ""
                if not prefix.strip():
                    targets.add(tok.line + tok.text.count("\n") + 1)
                for target in targets:
                    table.setdefault(target, set()).update(rules)

    # --- правила уровня объекта ---------------------------------------------

    def check_object(self, obj: L.StObject) -> None:
        fragments = list(_fragments(obj))
        if obj.kind == L.KIND_POU:
            self._check_header_comment(obj, fragments[0][1])
        self._check_names(obj, fragments)
        self._check_variables(obj, fragments)
        impls = [(rel, text) for role, rel, text in fragments if role.endswith("impl")]
        self._check_magic_numbers(obj, impls)
        self._check_cycle_counting(impls)

    def _check_header_comment(self, obj: L.StObject, rel: str) -> None:
        cfg = self.rule_cfg("STL001")
        tokens = L.tokenize(obj.decl)
        comments: list[str] = []
        for tok in tokens:
            if tok.kind == L.TK_COMMENT:
                comments.append(tok.text)
            elif tok.is_ident(*L.VAR_SECTION_KEYWORDS):
                break
        text = "\n".join(comments).lower()
        missing = [k for k in cfg.get("keywords", []) if k.lower() not in text]
        line = obj.header.line if obj.header else 1
        if missing:
            self.report("STL001", rel, line, 1, f"в заголовке POU нет: {', '.join(missing)}")
        elif cfg.get("require_docs_link", True) and "docs/" not in text:
            self.report("STL001", rel, line, 1, "в заголовке POU нет ссылки на документ в docs/")

    def _check_names(self, obj: L.StObject, fragments: list[tuple[str, str, str]]) -> None:
        cfg = self.rule_cfg("STL006")
        rel = fragments[0][1]
        line = obj.header.line if obj.header else 1
        kind = obj.kind
        if kind == L.KIND_POU:
            kind = obj.pou_kind or ""
        elif kind == L.KIND_DUT:
            kind = (obj.header.type_kind or "") if obj.header else ""
        elif kind == L.KIND_ITF:
            kind = "interface"
        prefixes = cfg.get(kind, [])
        if prefixes and not any(obj.name.startswith(p) and len(obj.name) > len(p) for p in prefixes):
            self.report("STL006", rel, line, 1, f"имя {obj.name}: ожидается префикс {' или '.join(prefixes)}")
        pattern = re.compile(cfg.get("member_pattern", "^[A-Z][A-Za-z0-9]*$"))
        exceptions = set(cfg.get("member_exceptions", []))
        members: list[tuple[str, str, L.DeclHeader | None]] = []
        members += [(m.name, L.SUFFIX_METHOD_DECL, m.header) for m in obj.methods]
        members += [(p.name, L.SUFFIX_PROP_DECL, p.header) for p in obj.properties]
        for name, suffix, header in members:
            if name in exceptions or pattern.match(name):
                continue
            self.report(
                "STL006",
                f"{obj.rel_dir()}/{name}{suffix}",
                header.line if header else 1,
                1,
                f"имя {name}: методы и свойства — PascalCase без префиксов",
            )

    def _check_variables(self, obj: L.StObject, fragments: list[tuple[str, str, str]]) -> None:
        cfg = self.rule_cfg("STL007")
        allow = set(cfg.get("allow_names", []))
        constant_re = re.compile(cfg.get("constant_pattern", "^[A-Z][A-Z0-9_]*$"))
        for role, rel, text in fragments:
            if role.endswith("impl"):
                continue
            decls: list[L.VarDecl] = []
            for block in L.parse_var_blocks(text):
                decls.extend(block.decls)
            if obj.kind == L.KIND_DUT:
                tdecl = L.parse_type_decl(text)
                if tdecl is not None:
                    decls.extend(tdecl.members)
            for decl in decls:
                constant = "CONSTANT" in decl.modifiers and decl.section in _CONSTANT_BLOCKS
                prefixes = expected_prefixes(decl.type_text, cfg)
                for name, _ in decl.names:
                    if name in allow:
                        continue
                    if constant:
                        if not constant_re.match(name):
                            self.report("STL007", rel, decl.line, 1, f"константа {name} — нужен UPPER_SNAKE_CASE")
                        continue
                    if prefixes is None or any(_has_prefix(name, p) for p in prefixes):
                        continue
                    self.report(
                        "STL007",
                        rel,
                        decl.line,
                        1,
                        f"переменная {name} : {decl.type_text} — ожидается префикс {_describe_prefixes(prefixes)}",
                    )

    def _check_magic_numbers(self, obj: L.StObject, impls: list[tuple[str, str]]) -> None:
        cfg = self.rule_cfg("STL008")
        if obj.name in cfg.get("exempt_objects", []):
            return
        allowed = {float(v) for v in cfg.get("allowed_values", [0, 1, 2])}
        for rel, text in impls:
            tokens = L.tokenize(text)
            sig = L.significant_indices(tokens)
            labels = set(L.case_label_indices(tokens, sig))
            depth = 0
            for k, index in enumerate(sig):
                tok = tokens[index]
                if tok.is_op("["):
                    depth += 1
                elif tok.is_op("]"):
                    depth = max(0, depth - 1)
                if tok.kind != L.TK_NUMBER or "#" in tok.text or depth > 0 or index in labels:
                    continue
                if k > 0 and tokens[sig[k - 1]].is_op("."):
                    continue
                value = float(tok.text.replace("_", ""))
                if value in allowed:
                    continue
                self.report(
                    "STL008",
                    rel,
                    tok.line,
                    tok.col,
                    f"магическое число {tok.text}: вынесите в GVL_Const (или // lint:allow STL008 причина)",
                )

    def _check_cycle_counting(self, impls: list[tuple[str, str]]) -> None:
        cfg = self.rule_cfg("STL011")
        name_re = re.compile(cfg.get("name_pattern", "(?i)(cycle|cyc|scan|tick)"))
        time_re = re.compile(cfg.get("time_name_pattern", "(?i)(time|delay|timeout)"))
        increments: list[tuple[str, str, int, int]] = []  # (designator, rel, line, col)
        compared_with_time: set[str] = set()
        for rel, text in impls:
            tokens = L.tokenize(text)
            sig = L.significant_indices(tokens)
            increments.extend((d, rel, line, col) for d, line, col in _increments(tokens, sig))
            compared_with_time |= _time_comparisons(tokens, sig, time_re)
        for designator, rel, line, col in increments:
            last = designator.split(".")[-1]
            if name_re.search(last):
                self.report(
                    "STL011",
                    rel,
                    line,
                    col,
                    f"{designator} := {designator} + 1 похоже на счёт циклов: время — через TON/TOF",
                )
            elif designator.lower() in compared_with_time:
                self.report(
                    "STL011",
                    rel,
                    line,
                    col,
                    f"{designator} считает циклы и сравнивается с временем: используйте таймер",
                )


def _offset_position(tok: L.Token, offset: int) -> tuple[int, int]:
    before = tok.text[:offset]
    newlines = before.count("\n")
    if newlines:
        return tok.line + newlines, len(before) - before.rfind("\n")
    return tok.line, tok.col + offset


def _fragments(obj: L.StObject) -> Iterator[tuple[str, str, str]]:
    """(роль, путь, текст) для каждого файла объекта; роль — по суффиксу файла."""
    for rel, text in L.object_files(obj):
        name = rel.rsplit("/", 1)[-1]
        suffix = name[name.index(".") :]
        role = {
            L.SUFFIX_IMPL: "impl",
            L.SUFFIX_METHOD_IMPL: "method.impl",
            L.SUFFIX_GET_IMPL: "get.impl",
            L.SUFFIX_SET_IMPL: "set.impl",
        }.get(suffix, "decl")
        yield role, rel, text


def prefix_for_type(type_text: str, cfg: dict[str, Any]) -> str | None:
    """Ожидаемый префикс переменной по тексту типа; None — тип не известен правилу."""
    text = type_text.strip()
    upper = text.upper()
    if upper.startswith("ARRAY"):
        return "a"
    if upper.startswith("POINTER TO"):
        return "p"
    if upper.startswith(("REFERENCE TO", "REF_TO")):
        return "ref"
    base = re.split(r"[\s(\[:]", text, maxsplit=1)[0]
    prefixes: dict[str, str] = cfg.get("type_prefixes", {})
    if base.upper() in prefixes:
        return prefixes[base.upper()]
    last = base.split(".")[-1]
    name_prefixes: dict[str, str] = cfg.get("type_name_prefixes", {})
    for type_prefix in sorted(name_prefixes, key=len, reverse=True):
        if last.startswith(type_prefix):
            return name_prefixes[type_prefix]
    if last.upper() in {t.upper() for t in cfg.get("fb_types", [])}:
        return "fb"
    return None


def _has_prefix(name: str, prefix: str) -> bool:
    """Имя начинается с префикса, за ним — заглавная буква или цифра (xReady, ai3Phase)."""
    rest = name[len(prefix) :]
    return name.startswith(prefix) and bool(rest) and (rest[0].isupper() or rest[0].isdigit())


def _describe_prefixes(prefixes: Sequence[str]) -> str:
    if len(prefixes) > 3:
        return "'a' или 'a' + префикс типа элемента"
    return " или ".join(f"'{p}'" for p in prefixes)


_ARRAY_OF_RE = re.compile(r"\s*OF\s+(.+)$", re.IGNORECASE | re.DOTALL)


def array_element_type(type_text: str) -> str | None:
    """Тип элемента массива: 'ARRAY[0..N - 1] OF ST_X' -> 'ST_X'; None — не массив или не разобран."""
    text = type_text.strip()
    if not text.upper().startswith("ARRAY"):
        return None
    pos = len("ARRAY")
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] != "[":
        return None
    depth = 0
    for i in range(pos, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                match = _ARRAY_OF_RE.match(text, i + 1)
                return match.group(1).strip() if match else None
    return None


def known_prefixes(cfg: dict[str, Any]) -> list[str]:
    """Все префиксы переменных из настроек правила (для составных префиксов массивов)."""
    found = {*cfg.get("type_prefixes", {}).values(), *cfg.get("type_name_prefixes", {}).values()}
    found |= {"fb", "p", "ref", "a"}
    return sorted(found, key=lambda p: (-len(p), p))


def expected_prefixes(type_text: str, cfg: dict[str, Any]) -> list[str] | None:
    """Допустимые префиксы переменной по типу; None — тип правилу не известен.

    Массив: 'a' и, по настройке array_element_prefixes, составной префикс 'a' + префикс элемента:
    astAlarm — ARRAY OF ST_*, afbAlarm — ARRAY OF FB_*, aitfDev — ARRAY OF I_*, altStart — ARRAY OF LTIME.
    """
    element = array_element_type(type_text)
    if element is None:
        prefix = prefix_for_type(type_text, cfg)
        return None if prefix is None else [prefix]
    mode = cfg.get("array_element_prefixes", "match")
    if mode == "off":
        return ["a"]
    nested = array_element_type(element) is not None
    inner = expected_prefixes(element, cfg) if mode == "match" or nested else None
    return ["a", *("a" + p for p in (inner or known_prefixes(cfg)))]


def _designator_text(tokens: Sequence[L.Token], sig: Sequence[int], a: int, b: int) -> str:
    return "".join(tokens[sig[j]].text for j in range(a, b + 1))


def _increments(tokens: Sequence[L.Token], sig: Sequence[int]) -> Iterator[tuple[str, int, int]]:
    """Операторы X := X + 1; / X := 1 + X; — (обозначение X, строка, столбец)."""
    n = len(sig)
    for k in range(n):
        if not tokens[sig[k]].is_op(":="):
            continue
        start = k - 1
        if start < 0 or tokens[sig[start]].kind != L.TK_IDENT:
            continue
        while start >= 2 and tokens[sig[start - 1]].is_op(".") and tokens[sig[start - 2]].kind == L.TK_IDENT:
            start -= 2
        lhs = _designator_text(tokens, sig, start, k - 1)
        end = k + 1
        while end < n and not tokens[sig[end]].is_op(";"):
            end += 1
        rhs = [tokens[sig[j]].text for j in range(k + 1, end)]
        rhs_text = "".join(rhs)
        if rhs_text.lower() in (f"{lhs}+1".lower(), f"1+{lhs}".lower()):
            first = tokens[sig[start]]
            yield lhs, first.line, first.col


def _time_comparisons(tokens: Sequence[L.Token], sig: Sequence[int], time_re: re.Pattern[str]) -> set[str]:
    """Обозначения, которые сравниваются с идентификатором «времени» (X >= T_DELAY)."""
    result: set[str] = set()
    for k in range(1, len(sig) - 1):
        if not tokens[sig[k]].is_op(*_COMPARISON_OPS):
            continue
        left = tokens[sig[k - 1]]
        right = tokens[sig[k + 1]]
        j = k + 1
        while j + 2 < len(sig) and tokens[sig[j + 1]].is_op(".") and tokens[sig[j + 2]].kind == L.TK_IDENT:
            j += 2
        right_last = tokens[sig[j]]
        if left.kind == L.TK_IDENT and right.kind == L.TK_IDENT and time_re.search(right_last.text):
            result.add(left.text.lower())
            i = k - 1
            parts = [left.text]
            while i >= 2 and tokens[sig[i - 1]].is_op(".") and tokens[sig[i - 2]].kind == L.TK_IDENT:
                parts.insert(0, tokens[sig[i - 2]].text)
                i -= 2
            result.add(".".join(parts).lower())
    return result


# ---------------------------------------------------------------------------
# Командная строка
# ---------------------------------------------------------------------------


def lint(root: str, config: dict[str, Any], paths: Sequence[str] | None = None) -> tuple[list[Finding], int]:
    """Проверяет раскладку; возвращает (замечания, число файлов)."""
    linter = Linter(root, config)
    findings = linter.run(list(paths) if paths else list(config["lint"]["paths"]))
    return findings, linter.files_checked


def _configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="st_lint.py", description="Линтер ST (правила CONTRIBUTING.md).")
    parser.add_argument("paths", nargs="*", help="каталоги раскладки от --root (по умолчанию из настроек)")
    parser.add_argument("--root", default=REPO_ROOT, help="корень репозитория")
    parser.add_argument("--config", default=None, help="файл настроек (по умолчанию tools/check/st_lint.toml)")
    parser.add_argument("--no-config", action="store_true", help="только настройки по умолчанию")
    parser.add_argument("--json", action="store_true", help="вывод JSON вместо текста")
    parser.add_argument("--strict", action="store_true", help="предупреждения тоже дают код 1")
    parser.add_argument("--list-rules", action="store_true", help="список правил")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configure_output()
    args = build_parser().parse_args(argv)
    if args.list_rules:
        for rule, text in RULES.items():
            print(f"{rule}  {text}")
        return 0
    config_path = None if args.no_config else (args.config or DEFAULT_CONFIG_PATH)
    if config_path == DEFAULT_CONFIG_PATH and not os.path.isfile(config_path):
        config_path = None
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        print(f"st_lint: {exc}", file=sys.stderr)
        return 2
    root = os.path.abspath(args.root)
    findings, files = lint(root, config, args.paths)
    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    if args.json:
        payload = {
            "version": 1,
            "findings": [asdict(f) for f in findings],
            "summary": {"files": files, "errors": errors, "warnings": warnings},
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for finding in findings:
            print(finding.format())
        print(f"st_lint: файлов {files}, ошибок {errors}, предупреждений {warnings}")
    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
