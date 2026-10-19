"""Привязка стенда к флагману КНС-1 (kns-pump-station) по снимку его интерфейса.

Снимок ``schema/source/flagship_symbols.json`` (``tools_project/flagship_snapshot.py``) содержит
объявления глобальных списков флагмана, типы флагмана и plc-process-lib и правила символьной
конфигурации OPC UA. Проверки без CODESYS и без флагмана:

- каждый путь каталога, белого списка, тегов эмулятора, узлов Telegraf и сгенерированного ST
  (``flagship/src``) — настоящая переменная флагмана, выгружаемая в символы, с тем же типом;
- SCADA и шлюз MQTT пишут только команды и задания: ``GVL_Hmi.st<DEV>Cmd``, ``GVL_Station.stStationCmd``,
  ``stLIC101Cmd`` — с правом ReadWrite в обеих сборках флагмана (``sim`` и ``site``), всё остальное
  только читается;
- копии файлов флагмана в ``schema/source/`` совпадают с SHA-256, записанными в снимке.

Живой прогон OPC UA с флагманом в CODESYS — docs/MANUAL_STEPS.md, раздел 11.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

import flagship_symbols as fs
import stack_catalog as sc

REPO = Path(__file__).resolve().parent.parent
FLAGSHIP_ST = REPO / "flagship" / "src"
COMMAND_ROOTS = (
    "Application.GVL_Hmi.",
    "Application.GVL_Station.stStationCmd.",
    "Application.GVL_Station.stLIC101Cmd.",
)
CONVERTIBLE = {"BOOL", "INT", "UINT", "UDINT", "WORD", "REAL"}


@pytest.fixture(scope="module")
def symbols() -> fs.FlagshipSymbols:
    return fs.load()


def test_snapshot_records_flagship_commit_and_sources(symbols: fs.FlagshipSymbols) -> None:
    meta = symbols.data["flagship"]
    assert meta["repository"] == "kns-pump-station"
    assert re.fullmatch(r"[0-9a-f]{40}", meta["commit"])
    assert meta["plc_process_lib"].startswith("plc-process-lib 1.0.0")
    for name in ("scada_tags.csv", "scada_alarms.csv"):
        text = (REPO / "schema" / "source" / name).read_text(encoding="utf-8")
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == meta["files"][f"scada/{name}"], name


def test_rules_cover_every_exported_list(symbols: fs.FlagshipSymbols) -> None:
    rules = {r["gvl"] for r in symbols.rules["rules"]}
    assert set(symbols.gvls) == rules
    assert {"GVL_Devices", "GVL_Hmi", "GVL_IO", "GVL_Station", "GVL_Log", "GVL_Persist"} <= rules


@pytest.mark.parametrize(
    ("path", "declared", "iec", "access"),
    [
        ("Application.GVL_Devices.fbP101.xRunning", "BOOL", "BOOL", "Read"),
        ("Application.GVL_Devices.fbLT101.stSts.rValue_eu", "REAL", "REAL", "Read"),
        ("Application.GVL_Devices.fbP101.stSts.stCommon.wAlmSuppressed", "WORD", "WORD", "Read"),
        ("Application.GVL_Hmi.stP101Cmd.rSpeedSp_pct", "REAL", "REAL", "ReadWrite"),
        ("Application.GVL_IO.xK1", "BOOL", "BOOL", "Read"),
        ("Application.GVL_Station.stStationSts.eMode", "E_StationMode", "INT", "Read"),
        ("Application.GVL_Station.stStationSts.eNe107", "PL.E_Ne107Status", "INT", "Read"),
        ("Application.GVL_Station.stStationCmd.xSetLevelPid", "BOOL", "BOOL", "ReadWrite"),
        ("Application.GVL_Station.fbLIC101.stSts.rOut_pct", "REAL", "REAL", "Read"),
        ("Application.GVL_Log.stEventFeed.udiFromSeq", "UDINT", "UDINT", "ReadWrite"),
        ("Application.GVL_Log.stEventFeed.udiSeqLast", "UDINT", "UDINT", "Read"),
    ],
)
def test_resolver_follows_flagship_declarations(
    symbols: fs.FlagshipSymbols, path: str, declared: str, iec: str, access: str
) -> None:
    sym = symbols.resolve(path)
    assert (sym.declared, sym.iec_type) == (declared, iec)
    assert sym.access == {"sim": access, "site": access}


def test_persist_settings_are_writable_only_in_simulation(symbols: fs.FlagshipSymbols) -> None:
    sym = symbols.resolve("Application.GVL_Persist.stStationCfg.rLvlStop_m")
    assert sym.access == {"sim": "ReadWrite", "site": "Read"}


@pytest.mark.parametrize(
    "path",
    [
        "Application.GVL_Const.STN_PUMP_COUNT",  # константы не выгружаются
        "Application.GVL_Devices.fbP101.stCmd",  # VAR_IN_OUT — ссылка, в символах нет
        "Application.GVL_Devices.fbP999.xRunning",
        "Application.GVL_Station.stStationSts.rNoSuchField",
        "GVL_IO.xK1",  # без Application.
    ],
)
def test_resolver_rejects_what_is_not_a_symbol(symbols: fs.FlagshipSymbols, path: str) -> None:
    with pytest.raises(fs.SymbolError):
        symbols.resolve(path)


def test_catalog_reads_real_flagship_symbols(symbols: fs.FlagshipSymbols) -> None:
    tags = {t.tag: t for t in sc.load_scada_tags()}
    for m in sc.load_catalog():
        if not m.plc_path:
            continue
        sym = symbols.resolve(m.plc_path)
        assert sym.readable("sim") and sym.readable("site"), m
        assert sym.iec_type == tags[m.scada_tag].data_type, m
        assert sym.iec_type in CONVERTIBLE, m
        if m.invert:
            assert sym.iec_type == "BOOL", m


def test_station_and_controller_are_in_catalog() -> None:
    pairs = {(m.device, m.metric) for m in sc.load_catalog()}
    for metric in ("mode", "method", "control", "ne107", "state", "pumps_required", "pumps_running"):
        assert ("KNS1", metric) in pairs
    for metric in ("pumps_available", "lead", "seq_remain", "level", "level_sp", "speed_sp"):
        assert ("KNS1", metric) in pairs
    for metric in ("pv", "sp", "out", "mode", "ne107"):
        assert ("LIC101", metric) in pairs
    k1 = next(m for m in sc.load_catalog() if (m.device, m.metric) == ("K1", "general_alarm"))
    assert k1.invert and k1.plc_path == "Application.GVL_IO.xK1"  # реле под напряжением в норме


def test_scada_writes_only_commands_and_setpoints(symbols: fs.FlagshipSymbols) -> None:
    """Белый список MQTT: только поля структур команд с правом записи в обеих сборках флагмана."""
    for e in sc.load_whitelist():
        assert e.plc_path.startswith(COMMAND_ROOTS), e
        sym = symbols.resolve(e.plc_path)
        assert sym.writable("sim") and sym.writable("site"), e
        assert sym.iec_type == ("BOOL" if e.value_type == "pulse" else "REAL"), e
    commands = {(e.device, e.command) for e in sc.load_whitelist()}
    for cmd in ("SetAuto", "SetManual", "SetStepped", "SetLevelPid", "AckAll", "ResetAll", "Silence"):
        assert ("KNS1", cmd) in commands
    assert {("LIC101", "SetAuto"), ("LIC101", "SetManual")} <= commands
    assert ("KNS1", "ExportLog") not in commands and ("KNS1", "RevertCfg") not in commands


def test_every_flagship_tag_matches_symbol_type_and_access(symbols: fs.FlagshipSymbols) -> None:
    """Теги эмулятора (scada_tags.csv, station_tags.csv): тип узла и право записи — как у символа флагмана."""
    for t in sc.load_scada_tags():
        sym = symbols.resolve(t.plc_path)
        assert sym.iec_type == t.data_type, t.tag
        writable = sym.writable("sim") and sym.writable("site")
        assert writable == (t.access == "RW"), t.tag
        if writable:
            assert t.plc_path.startswith(COMMAND_ROOTS), t.tag
        assert t.opcua_node_id == symbols.node_id(t.plc_path), t.tag


def test_station_alarms_follow_flagship_list() -> None:
    station = [a for a in sc.load_alarms() if a.device == "KNS1"]
    assert [a.code.split(".")[1] for a in station] == [
        "EHL",
        "DRY",
        "LACK",
        "NORES",
        "ATS",
        "FLOAT",
        "LDEV",
        "STEP",
        "NOAUTO",
        "UL1",
        "UL2",
        "UL3",
        "SIM",
    ]
    assert all(a.id == 100000 + a.slot and a.bit == a.slot - 1 for a in station)
    assert all(a.bit == a.slot for a in sc.load_alarms() if a.device != "KNS1")
    topics = sc.load_topics()
    for a in sc.load_alarms():
        assert re.fullmatch(topics["segments"]["suffix"], a.code.split(".", 1)[1]), a.code


def test_telegraf_nodes_are_readable_flagship_symbols(symbols: fs.FlagshipSymbols) -> None:
    text = (REPO / "telegraf" / "telegraf.d" / "opcua.conf").read_text(encoding="utf-8")
    nodes = re.findall(r'identifier = "\$\{OPCUA_ID_PREFIX\}([^"]+)"', text)
    assert len(nodes) == sum(1 for m in sc.load_catalog() if m.plc_path)
    for path in nodes:
        sym = symbols.resolve(path)
        assert sym.readable("sim") and sym.readable("site"), path
    assert 'INVERT = [("K1", "general_alarm")]' in text


def test_generated_st_binding_uses_real_symbols(symbols: fs.FlagshipSymbols) -> None:
    """FB_IiotKnsMap и PRG_Iiot (flagship/src) обращаются только к символам флагмана и константам библиотеки."""
    texts = {p: p.read_text(encoding="utf-8") for p in FLAGSHIP_ST.rglob("*.st")}
    assert texts, "нет flagship/src"
    paths: set[str] = set()
    for text in texts.values():
        paths |= fs.st_paths(text)
    assert len(paths) > 300
    for path in sorted(paths):
        symbols.resolve(path)
    apply_file = FLAGSHIP_ST / "POUs" / "Iiot" / "FB_IiotKnsMap" / "ApplyCommand.method.impl.st"
    apply = apply_file.read_text(encoding="utf-8")
    for target in re.findall(r"^\s+(GVL_\S+) :=", apply, re.M):
        sym = symbols.resolve("Application." + target)
        assert sym.writable("sim") and sym.writable("site"), target
    constants = set(re.findall(r"PL\.GVL_Const\.(\w+)", "".join(texts.values())))
    assert constants == {"MOT_FLT_COMM_LOSS", "MOT_WRN_COMM_LOSS"}
    assert constants <= set(symbols.data["pl_constants"])
    for enum, value in re.findall(r"PL\.(E_\w+)\.(\w+)", "".join(texts.values())):
        assert value in symbols.types[f"PL.{enum}"]["values"], (enum, value)


def test_core_st_has_no_flagship_references() -> None:
    """Ядро шлюза (src/, tests/) собирается без флагмана: нет KnsShim, GVL флагмана и типов PL.*."""
    for root in ("src", "tests"):
        for p in (REPO / root).rglob("*.st"):
            text = p.read_text(encoding="utf-8")
            assert not fs.st_paths(text), p
            assert "PL." not in re.sub(r"//.*", "", text), p
            assert "KnsShim" not in text, p
