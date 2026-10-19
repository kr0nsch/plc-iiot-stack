"""ПЛК-часть (ST в src/) и схема данных: одни и те же имена, коды и таблицы.

Проверки без CODESYS: сгенерированные таблицы актуальны, тексты кодов в ST совпадают с перечислениями
JSON Schema, настройки топиков по умолчанию — с schema/topics.json, config.json — с решениями проекта.
Поведение ST проверяют тесты coUnit в CODESYS (docs/TEST_REPORT.md).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema

import gen_plc_iiot
import stack_catalog as sc

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
SCHEMA = REPO / "schema"


def st_text(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def st_literals(rel: str) -> set[str]:
    """Строковые литералы, которые функция присваивает своему результату."""
    return set(re.findall(r":= '([^']*)';", st_text(rel)))


def schema(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((SCHEMA / name).read_text(encoding="utf-8"))
    return data


def test_generated_plc_tables_are_up_to_date() -> None:
    assert gen_plc_iiot.main(["--check"]) == 0, "запустите python tools_project/gen_plc_iiot.py"


def test_command_ack_reasons_match_schema() -> None:
    reasons = set(schema("command_ack.schema.json")["properties"]["reason"]["enum"])
    assert st_literals("POUs/Iiot/F_IiotCmdReasonText/F_IiotCmdReasonText.impl.st") == reasons


def test_cmd_result_names_match_schema() -> None:
    names = set(schema("command_ack.schema.json")["properties"]["cmd_result"]["enum"])
    assert st_literals("POUs/Iiot/F_IiotCmdResultText/F_IiotCmdResultText.impl.st") - {""} == names


def test_command_names_match_schema() -> None:
    names = set(schema("command.schema.json")["properties"]["command"]["enum"])
    text = st_text("POUs/Iiot/F_IiotCmdFromString/F_IiotCmdFromString.impl.st")
    assert set(re.findall(r"sCommand = '([^']*)'", text)) == names


def test_alarm_texts_match_schema() -> None:
    props = schema("alarm.schema.json")["properties"]
    assert st_literals("POUs/Iiot/F_IiotAlarmStateText/F_IiotAlarmStateText.impl.st") == set(props["state"]["enum"])
    assert st_literals("POUs/Iiot/F_IiotAlarmReasonText/F_IiotAlarmReasonText.impl.st") == set(props["reason"]["enum"])
    priorities = st_literals("POUs/Iiot/F_IiotAlarmPriorityText/F_IiotAlarmPriorityText.impl.st") - {""}
    assert priorities == set(props["priority"]["enum"])


def test_quality_texts_match_schema() -> None:
    quality = set(schema("telemetry.schema.json")["properties"]["quality"]["enum"])
    assert st_literals("POUs/Iiot/F_IiotQualityText/F_IiotQualityText.impl.st") == quality


def test_schema_version_and_ts_range_match_schema() -> None:
    const = st_text("GVLs/GVL_Const.gvl.st")
    version = re.search(r"IIOT_SCHEMA_VERSION : STRING\(\d+\) := '([^']+)';", const)
    assert version is not None
    assert re.match(schema("telemetry.schema.json")["properties"]["schema_version"]["pattern"], version.group(1))
    ts = schema("telemetry.schema.json")["properties"]["ts"]
    assert f"TS_MIN_MS : ULINT := {ts['minimum']};" in const
    assert f"TS_MAX_MS : ULINT := {ts['maximum']};" in const


def test_topic_defaults_match_station() -> None:
    station = schema("topics.json")["station"]
    cfg = st_text("DUTs/Iiot/ST_IiotCfg.dut.st")
    for field, key in (("sSite", "site"), ("sArea", "area"), ("sUnit", "unit"), ("sNode", "node")):
        assert re.search(rf"{field} : STRING\([^)]*\) := '{station[key]}';", cfg), field


def test_codesys_config_of_this_project() -> None:
    cfg = json.loads((REPO / "tools" / "codesys" / "config.json").read_text(encoding="utf-8"))
    assert cfg["modes"]["normal"]["tasks"][0] == {"name": "MainTask", "interval_ms": 20, "pous": ["PRG_Main"]}
    assert cfg["modes"]["normal"]["libraries"] == []
    assert cfg["modes"]["test"]["libraries"] == ["counit"]
    assert cfg["library"]["libraries"] == ["standard", "systimertc"]
    assert cfg["libraries"]["systimertc"]["placeholder"] == "SysTimeRtc"
    assert cfg["library"]["title"] == "plc-iiot-stack"
    assert set(cfg["library"]["exclude"]) == {"PRG_Main"}  # PRG_Iiot — во флагмане (flagship/)
    # библиотека CODESYS-MQTT в проект не подключается: её зависимости не собираются на 3.5.17.30
    assert "sd_mqtt" not in cfg["libraries"]


# --- точные сообщения ST (их сравнивают тесты coUnit) против JSON Schema -----------------------------------
TESTS = REPO / "tests"
EXPECTED_RE = re.compile(r"Expected\s*:=\s*(?P<expr>.*?),\s*Actual\s*:=\s*(?P<actual>[^;]*?)(?:,\s*Message|\);)", re.S)
ST_STRING_RE = re.compile(r"'((?:\$.|[^'$])*)'")


def st_unescape(text: str) -> str:
    """Строковый литерал ST: $' → ', $$ → $ (других экранирований в сообщениях JSON нет)."""
    return text.replace("$'", "'").replace("$$", "$")


def st_exact_messages() -> list[tuple[str, str | None, dict[str, Any]]]:
    """(файл, топик или None, JSON) — сообщения схемы, которые тесты coUnit сравнивают целиком."""
    out = []
    for path in sorted(TESTS.rglob("*.impl.st")):
        for m in EXPECTED_RE.finditer(path.read_text(encoding="utf-8")):
            text = "".join(st_unescape(s) for s in ST_STRING_RE.findall(m.group("expr")))
            if not text.startswith('{"schema_version"'):
                continue
            topic = re.search(r"sTopic\s*:=\s*'([^']*)'", m.group("actual"))
            out.append((path.relative_to(REPO).as_posix(), topic.group(1) if topic else None, json.loads(text)))
    return out


def message_class(topic: str | None, payload: dict[str, Any]) -> str:
    if topic is not None:
        found = sc.classify_topic(topic)
        assert found is not None, f"топик вне соглашения: {topic}"
        return found[0]
    assert {"node", "state", "reason"} <= set(payload), payload  # завещание (LWT) без топика в тесте
    return "status"


def test_st_exact_json_validates_against_schema() -> None:
    """Сообщения, которые ST формирует побайтно (сравнение строк в coUnit), соответствуют схемам."""
    messages = st_exact_messages()
    classes = {message_class(topic, payload) for _, topic, payload in messages}
    assert classes == {"telemetry", "alarm", "command_ack", "status"}, classes
    for file, topic, payload in messages:
        cls = message_class(topic, payload)
        validator = jsonschema.Draft202012Validator(schema(f"{cls}.schema.json"))
        errors = [e.message for e in validator.iter_errors(payload)]
        assert not errors, f"{file}: {topic}: {errors}"
