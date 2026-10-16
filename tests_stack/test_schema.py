"""JSON Schema сообщений, примеры и грамматика топиков (docs/data_schema.md, разделы 2–8)."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import stack_catalog as sc

CLASSES = ("telemetry", "alarm", "command", "command_ack", "status")
EXAMPLES = sorted((sc.SCHEMA_DIR / "examples").glob("*.json"))


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(sc.load_schema(name))


def is_valid(name: str, payload: dict[str, Any]) -> bool:
    return validator(name).is_valid(payload)


def example(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((sc.SCHEMA_DIR / "examples" / f"{name}.json").read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("name", CLASSES)
def test_schema_is_valid_draft_2020_12(name: str) -> None:
    schema = sc.load_schema(name)
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == f"urn:plc-iiot-stack:schema:{name}:1"
    assert schema["title"] and schema["description"]
    assert "schema_version" in schema["required"] and "ts" in schema["required"]


def test_common_fields_are_identical_in_all_schemas() -> None:
    """schema_version и ts объявлены одинаково (схемы самодостаточны, без ссылок между файлами)."""

    def strip(d: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in d.items() if k != "description"}

    base = sc.load_schema("telemetry")["properties"]
    for name in CLASSES:
        props = sc.load_schema(name)["properties"]
        assert strip(props["schema_version"]) == strip(base["schema_version"]), name
        assert strip(props["ts"]) == strip(base["ts"]), name


def test_every_class_has_examples() -> None:
    classes = {p.name.split(".")[0] for p in EXAMPLES}
    assert classes == set(CLASSES)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_matches_topic_class_and_schema(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    cls_name = path.name.split(".")[0]
    parsed = sc.classify_topic(data["topic"])
    assert parsed is not None, f"топик вне соглашения: {data['topic']}"
    topic_class, parts = parsed
    assert topic_class == cls_name
    cls = sc.load_topics()["classes"][cls_name]
    assert data["qos"] == cls["qos"] and data["retain"] == cls["retain"]
    errors = [e.message for e in validator(cls_name).iter_errors(data["payload"])]
    assert not errors, errors
    payload = data["payload"]
    st = sc.station()
    assert (parts["site"], parts["area"], parts["unit"]) == (st["site"], st["area"], st["unit"])
    if cls_name == "telemetry":
        assert (parts["device"], parts["metric"]) in {(m.device, m.metric) for m in sc.load_catalog()}
    elif cls_name == "alarm":
        assert payload["code"] == f"{parts['device']}.{parts['suffix']}"
        codes = {a.code: a for a in sc.load_alarms()}
        assert payload["code"] in codes
        assert payload["id"] == codes[payload["code"]].id
        assert payload["priority"] == codes[payload["code"]].priority
    elif cls_name in ("command", "command_ack"):
        assert payload["command"] == parts["command"]
    elif cls_name == "status":
        assert payload["node"] == parts["device"] == st["node"]


def test_example_commands_cover_whitelist_policy() -> None:
    allowed = {(e.device, e.command) for e in sc.load_whitelist()}
    assert ("P101", "Start") in allowed
    assert ("P101", "SpeedSp") in allowed
    assert ("P101", "SetOos") not in allowed
    ack = example("command_ack.P101.SetOos.not_whitelisted")["payload"]
    cmd = example("command.P101.SetOos")["payload"]
    assert ack["cmd_id"] == cmd["cmd_id"] and ack["reason"] == "not_whitelisted"


@pytest.mark.parametrize("version", ["1.0", "1.1", "1.12"])
def test_schema_version_minor_accepted(version: str) -> None:
    payload = copy.deepcopy(example("telemetry.LT101.level")["payload"])
    payload["schema_version"] = version
    assert is_valid("telemetry", payload)


@pytest.mark.parametrize("version", ["2.0", "1", "1.01", "v1.0", "1.0.0", ""])
def test_schema_version_other_major_or_format_rejected(version: str) -> None:
    payload = copy.deepcopy(example("telemetry.LT101.level")["payload"])
    payload["schema_version"] = version
    assert not is_valid("telemetry", payload)


def _mutate(base: dict[str, Any], **changes: Any) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in changes.items():
        if value is _DROP:
            out.pop(key, None)
        else:
            out[key] = value
    return out


_DROP = object()

NEGATIVE = [
    ("telemetry", "telemetry.LT101.level", {"schema_version": _DROP}, "нет версии схемы"),
    ("telemetry", "telemetry.LT101.level", {"ts": 1792137600}, "ts в секундах, а не мс"),
    ("telemetry", "telemetry.LT101.level", {"ts": 1792137600250.5}, "ts не целое"),
    ("telemetry", "telemetry.P101.running", {"value": True}, "логическое значение вместо 0/1"),
    ("telemetry", "telemetry.LT101.level", {"value": "2.31"}, "значение строкой"),
    ("telemetry", "telemetry.LT101.level", {"quality": "ok"}, "неизвестная достоверность"),
    ("alarm", "alarm.LT101.HH.activated", {"state": "Active"}, "неизвестное состояние"),
    ("alarm", "alarm.LT101.HH.activated", {"priority": "None"}, "приоритет None не публикуется"),
    ("alarm", "alarm.LT101.HH.activated", {"code": "lt101.hh"}, "код в нижнем регистре"),
    ("command", "command.P101.SpeedSp", {"value": 120.0}, "задание скорости больше 100 %"),
    ("command", "command.P101.SpeedSp", {"value": _DROP}, "команда-значение без value"),
    ("command", "command.P101.Start", {"value": 1}, "value у импульсной команды"),
    ("command", "command.P101.Start", {"extra": 1}, "лишнее поле в команде"),
    ("command", "command.P101.Start", {"cmd_id": "short"}, "короткий cmd_id"),
    ("command", "command.P101.Start", {"origin": "оператор"}, "кириллица в origin"),
    ("command", "command.P101.Start", {"command": "Explode"}, "неизвестная команда"),
    ("command_ack", "command_ack.P101.Start.accepted", {"reason": "not_whitelisted"}, "accepted с отказом"),
    ("command_ack", "command_ack.P101.SetOos.not_whitelisted", {"reason": "ok"}, "rejected с ok"),
    ("command_ack", "command_ack.P102.Start.device_rejected", {"cmd_result": _DROP}, "device_rejected без кода"),
    ("status", "status.PLC1.birth", {"reason": "lwt"}, "online с причиной lwt"),
    ("status", "status.PLC1.lwt", {"reason": "birth"}, "offline с причиной birth"),
]


@pytest.mark.parametrize(("cls", "base", "changes", "why"), NEGATIVE, ids=[n[3] for n in NEGATIVE])
def test_invalid_messages_rejected(cls: str, base: str, changes: dict[str, Any], why: str) -> None:
    payload = _mutate(example(base)["payload"], **changes)
    assert not is_valid(cls, payload), why


def test_mask_commands_need_integer_word() -> None:
    base = {"schema_version": "1.0", "cmd_id": "abcdef12", "ts": 1792137600000, "origin": "t", "command": "AckReq"}
    assert is_valid("command", {**base, "value": 5})
    assert not is_valid("command", {**base, "value": 65536})
    assert not is_valid("command", {**base, "value": 1.5})
    assert not is_valid("command", base)


def test_topic_patterns_are_built_from_segments() -> None:
    topics = sc.load_topics()
    seg = topics["segments"]
    head = "/".join(f"({seg[k]})" for k in ("site", "area", "unit", "device"))
    assert topics["classes"]["telemetry"]["pattern"] == f"^{head}/({seg['metric']})$"
    assert topics["classes"]["alarm"]["pattern"] == f"^{head}/alarm/({seg['suffix']})$"
    assert topics["classes"]["command"]["pattern"] == f"^{head}/cmd/({seg['command']})$"
    assert topics["classes"]["command_ack"]["pattern"] == f"^{head}/cmd_ack/({seg['command']})$"


@pytest.mark.parametrize(
    ("topic", "expected"),
    [
        ("vodokanal/kns1/station/LT101/level", "telemetry"),
        ("vodokanal/kns1/station/LT101/alarm/HH", "alarm"),
        ("vodokanal/kns1/station/P101/cmd/Start", "command"),
        ("vodokanal/kns1/station/P101/cmd_ack/Start", "command_ack"),
        ("vodokanal/kns1/station/PLC1/status/connection", "status"),
        ("vodokanal/kns1/station/lt101/level", None),
        ("vodokanal/kns1/station/LT101/Level", None),
        ("vodokanal/kns1/LT101/level", None),
        ("vodokanal/kns1/station/LT101/level/extra/more", None),
        ("vodokanal/kns1/station/PLC1/status/online", None),
    ],
)
def test_topic_classification(topic: str, expected: str | None) -> None:
    parsed = sc.classify_topic(topic)
    assert (parsed[0] if parsed else None) == expected


def test_subscription_filters_do_not_overlap() -> None:
    """Подписка класса ловит только свой класс: телеметрия — 5 уровней, остальное — 6."""
    classes = sc.load_topics()["classes"]

    def matches(filt: str, topic: str) -> bool:
        f, t = filt.split("/"), topic.split("/")
        return len(f) == len(t) and all(a in ("+", b) for a, b in zip(f, t, strict=True))

    samples = {
        "telemetry": "vodokanal/kns1/station/LT101/level",
        "alarm": "vodokanal/kns1/station/LT101/alarm/HH",
        "command": "vodokanal/kns1/station/P101/cmd/Start",
        "command_ack": "vodokanal/kns1/station/P101/cmd_ack/Start",
        "status": "vodokanal/kns1/station/PLC1/status/connection",
    }
    for name, cls in classes.items():
        for other, topic in samples.items():
            assert matches(cls["filter"], topic) == (name == other), (name, other)


def test_reserved_metric_names_are_class_keywords() -> None:
    topics = sc.load_topics()
    keywords = set()
    for cls in topics["classes"].values():
        keywords |= set(re.findall(r"/([a-z_]+)/\(", cls["pattern"]))
    assert keywords == {"alarm", "cmd", "cmd_ack", "status"}
    assert set(topics["reserved_metrics"]) == keywords
