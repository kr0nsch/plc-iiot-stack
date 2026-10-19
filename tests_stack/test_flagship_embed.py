"""Встраивание ПЛК-части во флагман (tools_project/flagship_embed.py) и сверка с живым OPC UA-сервером
(tools_project/opcua_live_check.py): чистые функции на модели рабочей копии флагмана, без CODESYS."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import flagship_embed as fe
import flagship_symbols as fs
import opcua_live_check as olc

FLAGSHIP_CONST = """\
// Назначение: константы проекта
{attribute 'qualified_only'}
VAR_GLOBAL CONSTANT
    // ===== Инфраструктура (К3) =====
    LOG_CAPACITY : UINT := 200;              // записей в кольце журнала
    TAG_LEN : INT := 24;
END_VAR
"""

FLAGSHIP_CONFIG = """\
{
  "modes": {
    "normal": {
      "tasks": [
        {"name": "MainTask", "interval_ms": 20,
         "pous": ["PRG_FieldIn", "PRG_Station", "PRG_Devices", "PRG_FieldOut"]},
        {"name": "SlowTask", "interval_ms": 200, "pous": ["PRG_Slow"]}
      ]
    }
  },
  "library": {
    "exclude": ["PRG_FieldIn", "PRG_Station", "PRG_Devices", "PRG_FieldOut",
                "PRG_Slow"]
  }
}
"""

FLAGSHIP_RULES = """\
{
  "builds": ["sim", "site"],
  "rules": [
    {"gvl": "GVL_Devices", "vars": ["fb*"], "access": "Read"},
    {"gvl": "GVL_Time", "vars": ["lrMainNow_s"], "access": "Read"}
  ],
  "types": []
}
"""


@pytest.fixture
def flagship(tmp_path: Path) -> Path:
    for rel, text in (
        (fe.CONST_FILE, FLAGSHIP_CONST),
        (fe.CONFIG_FILE, FLAGSHIP_CONFIG),
        (fe.RULES_FILE, FLAGSHIP_RULES),
    ):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    return tmp_path


def test_embed_copies_core_binding_and_tests(flagship: Path) -> None:
    report = fe.embed(flagship)
    assert (flagship / "src/POUs/Iiot/PRG_Iiot/PRG_Iiot.decl.st").is_file()
    assert (flagship / "src/POUs/Iiot/FB_IiotKnsMap/ApplyCommand.method.impl.st").is_file()
    assert (flagship / "src/POUs/Iiot/FB_MqttCommands/FB_MqttCommands.decl.st").is_file()
    assert (flagship / "src/GVLs/Generated/GVL_IiotMap.gvl.st").is_file()
    assert not (flagship / "src/POUs/PRG_Main").exists(), "у флагмана свои программы задач"
    assert (flagship / "tests/POUs/Iiot/FB_MqttClientFake/Inject.method.decl.st").is_file()
    assert (flagship / "tests/POUs/Iiot/FB_IiotKnsMap_Test/FB_IiotKnsMap_Test.decl.st").is_file()
    assert (flagship / "tests/DUTs/Iiot/ST_FakeMqttMsg.dut.st").is_file()
    assert not (flagship / "tests/POUs/Iiot/PRG_Tests").exists()
    gvl = (flagship / fe.TESTS_GVL).read_text(encoding="utf-8")
    assert "{attribute 'linkalways'}" in gvl
    assert "fbIiotKnsMapTest     : FB_IiotKnsMap_Test;" in gvl
    assert "fbJsonBuilderTest" in gvl
    assert report.written and fe.embed(flagship).written == [], "повторный запуск ничего не меняет"


def test_constants_section_is_merged_once(flagship: Path) -> None:
    fe.embed(flagship, with_tests=False)
    text = (flagship / fe.CONST_FILE).read_text(encoding="utf-8")
    assert text.count(fe.CONST_BEGIN) == 1 and text.count(fe.CONST_END) == 1
    assert "LOG_CAPACITY : UINT := 200;" in text and "MQTT_TOPIC_LEN : UINT := 127;" in text
    assert text.rstrip().endswith("END_VAR") and text.count("END_VAR") == 1
    again = fe.merge_constants(text, (fe.REPO / fe.CONST_FILE).read_text(encoding="utf-8"))
    assert again == text


def test_constant_name_clash_is_an_error() -> None:
    clash = FLAGSHIP_CONST.replace("TAG_LEN : INT := 24;", "MQTT_TOPIC_LEN : UINT := 99;")
    with pytest.raises(fe.EmbedError, match="MQTT_TOPIC_LEN"):
        fe.merge_constants(clash, (fe.REPO / fe.CONST_FILE).read_text(encoding="utf-8"))


def test_config_and_symbol_rules_patched(flagship: Path) -> None:
    fe.embed(flagship, with_tests=False)
    cfg = json.loads((flagship / fe.CONFIG_FILE).read_text(encoding="utf-8"))
    pous = cfg["modes"]["normal"]["tasks"][0]["pous"]
    assert pous == ["PRG_FieldIn", "PRG_Station", "PRG_Devices", "PRG_Iiot", "PRG_FieldOut"]
    assert "PRG_Iiot" in cfg["library"]["exclude"]
    rules = json.loads((flagship / fe.RULES_FILE).read_text(encoding="utf-8"))["rules"]
    assert rules[-1] == fe.SYMBOL_RULE and len(rules) == 3
    text = (flagship / fe.RULES_FILE).read_text(encoding="utf-8")
    assert '    {"gvl": "GVL_Iiot", "vars": ["stIiotCfg", "stIiotSts"], "access": "Read"}\n  ]' in text


def test_not_a_flagship(tmp_path: Path) -> None:
    with pytest.raises(fe.EmbedError, match="не рабочая копия"):
        fe.embed(tmp_path)


def test_main_reports_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert fe.main(["--repo", str(tmp_path)]) == 1
    assert "не рабочая копия" in capsys.readouterr().err


# --- opcua_live_check: без сервера ------------------------------------------------------------------------
def test_expected_variant_for_catalog_nodes() -> None:
    """Каждому узлу каталога по снимку флагмана сопоставлен тип OPC UA; перечисления — Int16."""
    symbols = fs.load()
    paths = [p for _, _, p, _ in olc.catalog_paths()]
    assert len(paths) == 133
    variants = {olc.expected_variant(symbols.resolve(p).iec_type) for p in paths}
    assert None not in variants
    assert olc.expected_variant(symbols.resolve("Application.GVL_Station.stStationSts.eMode").iec_type) == "Int16"
    counts, problems = olc.check_types(paths, dict.fromkeys(paths, "Null"), symbols)
    assert counts == {"Null": 133} and len(problems) == 133


def test_live_check_helpers() -> None:
    assert olc.find_iec_namespace(["http://opcfoundation.org/UA/", "x", "CODESYSSPV3/3S/IecVarAccess"]) == 2
    with pytest.raises(olc.CheckError):
        olc.find_iec_namespace(["http://opcfoundation.org/UA/"])
    assert olc.id_prefix("CODESYS Control Win V3") == "|var|CODESYS Control Win V3."
    assert [len(c) for c in olc.chunks(list(range(133)), 100)] == [100, 33]
    assert olc.expected_variant("STRING(31)") == "String"
