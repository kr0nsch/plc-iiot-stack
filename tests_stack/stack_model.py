"""Модель хранения и разбор ссылок Flux для тестов согласованности стенда.

Модель InfluxDB (measurement → теги и поля) читается из таблицы docs/data_schema.md между метками
``<!-- BEGIN: influx-model -->`` и ``<!-- END: influx-model -->``: тесты сверяют с документом,
а не с собственной копией списка.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import stack_catalog as sc

# Столбцы, которые есть у каждой записи Flux
FLUX_BUILTIN_COLUMNS = frozenset({"_measurement", "_field", "_value", "_time", "_start", "_stop"})
TYPE_ALIASES = {"float": "float", "int": "integer", "integer": "integer", "string": "string", "bool": "boolean"}


@dataclass
class MeasurementModel:
    name: str
    bucket: str
    tags: set[str] = field(default_factory=set)
    fields: dict[str, str] = field(default_factory=dict)  # поле → тип (float, integer, string)


def load_influx_model(root: Path = sc.REPO) -> dict[str, MeasurementModel]:
    text = (root / "docs" / "data_schema.md").read_text(encoding="utf-8")
    match = re.search(r"<!-- BEGIN: influx-model -->\n(.*?)<!-- END: influx-model -->", text, re.S)
    if not match:
        raise AssertionError("docs/data_schema.md: нет таблицы influx-model")
    model: dict[str, MeasurementModel] = {}
    for line in match.group(1).splitlines():
        if not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        name = re.findall(r"`([^`]+)`", cells[0])[0]
        bucket = re.findall(r"`([^`]+)`", cells[1])[0]
        m = MeasurementModel(name, bucket)
        m.tags = set(re.findall(r"`([^`]+)`", cells[3]))
        for fname, ftype in re.findall(r"`([^`]+)`\s*\((\w+)\)", cells[4]):
            m.fields[fname] = ftype
        model[name] = m
    return model


@dataclass
class FluxRefs:
    """Что запрос Flux берёт из базы."""

    measurements: set[str] = field(default_factory=set)
    fields: set[str] = field(default_factory=set)
    columns: set[str] = field(default_factory=set)  # r.<имя> в предикатах
    eq: dict[str, set[str]] = field(default_factory=dict)  # r.<имя> == "литерал"
    listed_columns: set[str] = field(default_factory=set)  # keep/group/pivot/sort/rename
    renamed_to: set[str] = field(default_factory=set)
    variables: set[str] = field(default_factory=set)  # ${var} и ${var:format}
    regexes: dict[str, list[str]] = field(default_factory=dict)  # r.<имя> =~ /.../


R_EQ = re.compile(r"\br\.([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=)\s*\"([^\"]*)\"")
R_COL = re.compile(r"\br\.([A-Za-z_][A-Za-z0-9_]*)")
R_RE = re.compile(r"\br\.([A-Za-z_][A-Za-z0-9_]*)\s*=~\s*/((?:[^/\\]|\\.)*)/")
R_LIST = re.compile(r"\b(?:columns|rowKey|columnKey)\s*:\s*\[([^\]]*)\]")
R_RENAME = re.compile(r"rename\(columns:\s*\{([^}]*)\}\)")
R_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::[a-z]+)?\}")


def flux_refs(query: str) -> FluxRefs:
    refs = FluxRefs()
    for name, op, value in R_EQ.findall(query):
        if op == "==":
            refs.eq.setdefault(name, set()).add(value)
    refs.measurements = refs.eq.get("_measurement", set())
    refs.fields = refs.eq.get("_field", set())
    refs.columns = set(R_COL.findall(query))
    for name, pattern in R_RE.findall(query):
        refs.regexes.setdefault(name, []).append(pattern)
    for body in R_LIST.findall(query):
        refs.listed_columns |= set(re.findall(r"\"([^\"]+)\"", body))
    for body in R_RENAME.findall(query):
        for old, new in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\"([^\"]+)\"", body):
            refs.listed_columns.add(old)
            refs.renamed_to.add(new)
    refs.variables = set(R_VAR.findall(query))
    return refs


def env_refs(text: str) -> set[str]:
    """Имена переменных окружения ${VAR}, ${VAR:-…}, ${VAR:?…} в тексте конфигурации."""
    return set(re.findall(r"(?<!\$)\$\{([A-Za-z_][A-Za-z0-9_]*)", text))
