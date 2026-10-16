"""Каталог телеметрии, белый список команд и перечень тревог против выхода iolistgen."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

import stack_catalog as sc

# Единицы перечня (русские) → единицы каталога (ASCII)
UNIT_MAP = {
    "м": "m",
    "бар": "bar",
    "м³/ч": "m3/h",
    "А": "A",
    "мг/м³": "mg/m3",
    "% НКПР": "%LEL",
    "°C": "degC",
    "%": "%",
    "ч": "h",
    "с": "s",
    "": "",
}
DIAG_NODE = sc.station()["node"]


@pytest.fixture(scope="module")
def tags() -> dict[str, sc.ScadaTag]:
    return {t.tag: t for t in sc.load_scada_tags()}


def test_catalog_keys_unique_and_named_by_rules() -> None:
    catalog = sc.load_catalog()
    seg = sc.load_topics()["segments"]
    reserved = set(sc.load_topics()["reserved_metrics"])
    dup = [k for k, n in Counter((m.device, m.metric) for m in catalog).items() if n > 1]
    assert not dup
    for m in catalog:
        assert re.fullmatch(seg["device"], m.device), m
        assert re.fullmatch(seg["metric"], m.metric), m
        assert m.metric not in reserved, m
        assert m.kind in sc.KINDS, m
        assert m.description, m


def test_catalog_kinds_are_consistent() -> None:
    for m in sc.load_catalog():
        if m.kind == "analog":
            assert m.unit and m.deadband and m.deadband > 0, m
        if m.kind in ("discrete", "enum"):
            assert m.deadband is None and not m.unit, m


def test_catalog_follows_iolistgen_tags(tags: dict[str, sc.ScadaTag]) -> None:
    for m in sc.load_catalog():
        if m.device == DIAG_NODE:
            assert not m.scada_tag and not m.plc_path, "диагностика шлюза — без пути из перечня"
            continue
        t = tags.get(m.scada_tag)
        assert t is not None, f"{m.device}/{m.metric}: нет тега {m.scada_tag} в scada_tags.csv"
        assert t.access == "R", m
        assert t.plc_path == m.plc_path, m
        assert (t.eng_min, t.eng_max) == (m.eng_min, m.eng_max), m
        assert UNIT_MAP[t.units] == m.unit, f"{m.scada_tag}: {t.units!r} → {m.unit!r}"
        if t.device:
            assert t.device == m.device, m
        if m.kind == "discrete":
            assert t.data_type == "BOOL", m
        if m.kind in ("enum", "counter", "integer"):
            assert t.data_type in ("INT", "UINT", "UDINT", "WORD", "REAL"), m


def test_catalog_has_metrics_used_by_dashboards() -> None:
    pairs = {(m.device, m.metric) for m in sc.load_catalog()}
    for pump in ("P101", "P102", "P103"):
        for metric in ("running", "state", "mode", "speed", "run_hours", "starts", "starts_last_hour"):
            assert (pump, metric) in pairs
    for pair in [("LT101", "level"), ("PT201", "pressure"), ("FT202", "flow"), ("K1", "general_alarm")]:
        assert pair in pairs


def test_every_device_of_iolistgen_is_known(tags: dict[str, sc.ScadaTag]) -> None:
    """Устройства каталога (кроме узла и сигналов без ФБ) есть в перечне, и тип совпадает."""
    devices = {t.device: t.device_type for t in tags.values() if t.device}
    for m in sc.load_catalog():
        if m.device in (DIAG_NODE, "K1"):
            continue
        assert m.device in devices, m


def test_whitelist_entries_follow_iolistgen(tags: dict[str, sc.ScadaTag]) -> None:
    schema_commands = set(sc.load_schema("command")["properties"]["command"]["enum"])
    wl = sc.load_whitelist()
    assert not [k for k, n in Counter((e.device, e.command) for e in wl).items() if n > 1]
    for e in wl:
        assert e.command in schema_commands, e
        assert e.value_type in sc.VALUE_TYPES, e
        t = tags.get(e.scada_tag)
        assert t is not None and t.access == "RW", e
        assert t.plc_path == e.plc_path, e
        assert e.scada_tag == f"{e.device}.Cmd.{e.command}", e
        if e.value_type == "number":
            assert e.min is not None and e.max is not None and e.min < e.max, e
        else:
            assert e.min is None and e.max is None, e
            assert t.data_type == "BOOL", e


def test_whitelist_policy_is_minimal() -> None:
    """Действия обслуживания (вывод из работы, подмена, маски тревог, сброс ТО) — только с местной HMI."""
    forbidden = {"SetOos", "ResetMaint", "SubstValue", "AckReq", "ShelveReq", "UnshelveReq"}
    assert not forbidden & {e.command for e in sc.load_whitelist()}
    speed = [e for e in sc.load_whitelist() if e.command == "SpeedSp"]
    assert {e.device for e in speed} == {"P101", "P102", "P103"}
    assert all((e.min, e.max) == (0.0, 100.0) for e in speed)


def test_alarm_list_matches_schema_rules() -> None:
    schema = sc.load_schema("alarm")["properties"]
    seg = sc.load_topics()["segments"]
    alarms = sc.load_alarms()
    assert len({a.id for a in alarms}) == len(alarms)
    for a in alarms:
        assert re.fullmatch(schema["code"]["pattern"], a.code), a
        device, suffix = a.code.split(".")
        assert device == a.device and re.fullmatch(seg["suffix"], suffix), a
        assert a.priority in schema["priority"]["enum"], a
        assert schema["id"]["minimum"] <= a.id <= schema["id"]["maximum"], a


def test_alarm_text_lookup_covers_every_alarm() -> None:
    lookup = json.loads((sc.REPO / "telegraf" / "lookup" / "alarm_texts.json").read_text(encoding="utf-8"))
    assert set(lookup) == {a.code for a in sc.load_alarms()}
    assert all(set(v) == {"text"} and v["text"] for v in lookup.values())


SHARED_FILES = [
    *(sc.SCHEMA_DIR / "source").glob("*.csv"),
    sc.SCHEMA_DIR / "telemetry_catalog.csv",
    sc.SCHEMA_DIR / "command_whitelist.csv",
    sc.SCHEMA_DIR / "topics.json",
]
SKIP_DIRS = {".git", "build", ".venv", "venv", "node_modules", "__pycache__"}


@pytest.mark.parametrize("source", SHARED_FILES, ids=lambda p: p.name)
def test_copies_of_contract_files_are_identical(source: Path) -> None:
    """Копии контракта в пакетах (эмулятор, отчёт) совпадают с schema/ байт в байт."""
    original = source.read_bytes()
    for path in sc.REPO.rglob(source.name):
        rel = path.relative_to(sc.REPO)
        if rel.parts[0] == "schema" or SKIP_DIRS & set(rel.parts):
            continue
        assert path.read_bytes() == original, f"{rel.as_posix()} отличается от schema/: скопируйте заново"
