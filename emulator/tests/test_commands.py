"""Шлюз команд MQTT: белый список, диапазоны, отказы по составу, повторам и возрасту."""

from __future__ import annotations

import json
from typing import Any

import pytest

from iiot_emulator.commands import CommandGateway
from iiot_emulator.schema import command_whitelist, default_topics

NOW = 1_792_137_620_000
TOPICS = default_topics()


def cmd(device: str, name: str, value: object = None, **over: Any) -> tuple[str, bytes]:
    body: dict[str, Any] = {
        "schema_version": "1.0",
        "cmd_id": over.pop("cmd_id", f"id-{device}-{name}-{value}-{len(over)}".replace(".", "_")[:36]),
        "ts": NOW,
        "origin": "operator1@test",
        "command": name,
    }
    if value is not None:
        body["value"] = value
    body.update(over)
    body = {k: v for k, v in body.items() if v is not _DROP}
    return TOPICS.prefix + f"/{device}/cmd/{name}", json.dumps(body).encode()


_DROP = object()


def check(gw: CommandGateway, topic: str, payload: bytes, *, retained: bool = False, now: int = NOW) -> tuple[str, Any]:
    d = gw.check(topic, payload, retained=retained, now_ms=now)
    return d.reason, d


@pytest.fixture
def gw() -> CommandGateway:
    return CommandGateway(TOPICS, max_age_s=30.0, rate_limit=3, rate_window_s=10.0)


def test_whitelisted_pulse_passes(gw: CommandGateway) -> None:
    reason, d = check(gw, *cmd("P101", "Start"))
    assert reason == "ok"
    assert d.entry.scada_tag == "P101.Cmd.Start"


@pytest.mark.parametrize(
    ("device", "command"),
    [
        ("P101", "SetOos"),  # вывод из работы — только с местного HMI
        ("P101", "ResetMaint"),
        ("LT101", "SubstValue"),  # подмена по MQTT запрещена
        ("LT101", "SetManual"),
        ("LS103", "SetOos"),
        ("V1", "SpeedSp"),  # у вентилятора нет ПЧ
        ("P101", "AckReq"),
        ("PLC1", "Reset"),  # не устройство
        ("P999", "Start"),
    ],
)
def test_not_whitelisted(gw: CommandGateway, device: str, command: str) -> None:
    value = {"SubstValue": 1.0, "SpeedSp": 50.0, "AckReq": 1}.get(command)
    reason, _ = check(gw, *cmd(device, command, value))
    assert reason == "not_whitelisted"


@pytest.mark.parametrize("value", [-0.1, 100.01, 150, -50])
def test_speed_out_of_range(gw: CommandGateway, value: float) -> None:
    reason, _ = check(gw, *cmd("P102", "SpeedSp", value))
    assert reason == "out_of_range"


@pytest.mark.parametrize("value", [0, 60.5, 100])
def test_speed_in_range(gw: CommandGateway, value: float) -> None:
    reason, d = check(gw, *cmd("P102", "SpeedSp", value))
    assert reason == "ok" and d.value == float(value)


def test_payload_errors(gw: CommandGateway) -> None:
    topic, _ = cmd("P101", "Start")
    assert check(gw, *cmd("P101", "Start", schema_version="2.0", cmd_id="vvvvvvvv01"))[0] == "unsupported_version"
    assert check(gw, *cmd("P101", "Start", schema_version=1, cmd_id="vvvvvvvv02"))[0] == "invalid_payload"
    assert check(gw, *cmd("P101", "Start", value=1, cmd_id="vvvvvvvv03"))[0] == "invalid_payload"
    assert check(gw, *cmd("P101", "SpeedSp", cmd_id="vvvvvvvv04"))[0] == "invalid_payload"
    assert check(gw, *cmd("P101", "SpeedSp", "fast", cmd_id="vvvvvvvv05"))[0] == "invalid_payload"
    assert check(gw, *cmd("P101", "Start", extra=1, cmd_id="vvvvvvvv06"))[0] == "invalid_payload"
    assert check(gw, *cmd("P101", "Start", origin="оператор", cmd_id="vvvvvvvv07"))[0] == "invalid_payload"
    assert check(gw, *cmd("P101", "Start", ts=_DROP, cmd_id="vvvvvvvv08"))[0] == "invalid_payload"
    assert check(gw, *cmd("P101", "Start", command="Launch", cmd_id="vvvvvvvv09"))[0] == "invalid_payload"
    # команда в теле не совпадает с топиком
    assert check(gw, topic, cmd("P101", "Stop", cmd_id="vvvvvvvv10")[1])[0] == "topic_mismatch"


def test_unanswerable_messages_are_dropped(gw: CommandGateway) -> None:
    topic, _ = cmd("P101", "Start")
    for payload in (b"not json", b"[1,2]", json.dumps({"command": "Start"}).encode(), b'{"cmd_id":"x"}'):
        d = gw.check(topic, payload, retained=False, now_ms=NOW)
        assert d.cmd_id is None and not d.passed
    d = gw.check("other/site/x/P101/cmd/Start", cmd("P101", "Start")[1], retained=False, now_ms=NOW)
    assert d.cmd_id is None
    assert gw.stats.dropped == 5


def test_retained_expired_duplicate_rate(gw: CommandGateway) -> None:
    assert check(gw, *cmd("P101", "Start", cmd_id="retained-001"), retained=True)[0] == "retained"
    assert check(gw, *cmd("P101", "Start", cmd_id="expired-0001"), now=NOW + 31_000)[0] == "expired"
    assert check(gw, *cmd("P101", "Start", cmd_id="future-00001"), now=NOW - 31_000)[0] == "expired"
    assert check(gw, *cmd("P101", "Start", cmd_id="unique-00001"))[0] == "ok"
    assert check(gw, *cmd("P101", "Start", cmd_id="unique-00001"))[0] == "duplicate"
    assert check(gw, *cmd("P101", "Stop", cmd_id="unique-00002"))[0] == "ok"
    assert check(gw, *cmd("P101", "Ack", cmd_id="unique-00003"))[0] == "ok"
    assert check(gw, *cmd("P101", "Reset", cmd_id="unique-00004"))[0] == "rate_limited"  # 3 за 10 с
    assert check(gw, *cmd("P102", "Reset", cmd_id="unique-00005"))[0] == "rate_limited"  # лимит — на узел
    assert check(gw, *cmd("P101", "Reset", cmd_id="unique-00006"), now=NOW + 10_001)[0] == "ok"


def test_duplicate_memory_is_last_16() -> None:
    gw = CommandGateway(TOPICS, rate_limit=1000)
    assert check(gw, *cmd("P101", "Ack", cmd_id="first-000001"))[0] == "ok"
    for i in range(15):
        assert check(gw, *cmd("P101", "Ack", cmd_id=f"other-{i:06d}"))[0] == "ok"
    assert check(gw, *cmd("P101", "Ack", cmd_id="first-000001"))[0] == "duplicate"  # 16-я с конца
    assert check(gw, *cmd("P101", "Ack", cmd_id="other-x00016"))[0] == "ok"
    assert check(gw, *cmd("P101", "Ack", cmd_id="first-000001"))[0] == "ok"  # вытеснена из памяти


def test_check_order_follows_data_schema(gw: CommandGateway) -> None:
    """Первая ошибка по порядку раздела 5.1: состав раньше версии, версия раньше топика и списка."""
    topic, _ = cmd("P101", "SetOos")
    body = cmd("P101", "SetOos", schema_version="2.0", extra=1, cmd_id="order-000001")[1]
    assert check(gw, topic, body)[0] == "invalid_payload"
    body = cmd("P101", "Stop", schema_version="2.0", cmd_id="order-000002")[1]
    assert check(gw, topic, body)[0] == "unsupported_version"
    body = cmd("P101", "Stop", cmd_id="order-000003")[1]
    assert check(gw, topic, body)[0] == "topic_mismatch"
    old = cmd("P101", "SetOos", cmd_id="order-000004", ts=NOW - 60_000)
    assert check(gw, *old)[0] == "not_whitelisted"  # список раньше возраста


def test_every_whitelist_entry_passes_and_schema_agrees(gw: CommandGateway, validators: dict[str, Any]) -> None:
    gw.rate_limit = 10_000
    for i, e in enumerate(command_whitelist().values()):
        value = None
        if e.value_type == "number":
            value = (e.min or 0.0) + 1.0
        topic, payload = cmd(e.device, e.command, value, cmd_id=f"wl-{i:08d}")
        validators["command"].validate(json.loads(payload))
        reason, _ = check(gw, topic, payload)
        assert reason == "ok", (e, reason)


SCHEMA_CORPUS: list[dict[str, Any]] = [
    {"schema_version": "1.0", "cmd_id": "corpus-001", "ts": NOW, "origin": "a@b", "command": "Start"},
    {"schema_version": "1.3", "cmd_id": "corpus-002", "ts": NOW, "origin": "a@b", "command": "Stop"},
    {"schema_version": "1.0", "cmd_id": "corpus-003", "ts": NOW, "origin": "a@b", "command": "Start", "value": 1},
    {"schema_version": "1.0", "cmd_id": "corpus-004", "ts": NOW, "origin": "a@b", "command": "SpeedSp"},
    {"schema_version": "1.0", "cmd_id": "corpus-005", "ts": NOW, "origin": "a@b", "command": "SpeedSp", "value": 101},
    {"schema_version": "1.0", "cmd_id": "corpus-006", "ts": NOW, "origin": "a@b", "command": "SpeedSp", "value": 55.5},
    {"schema_version": "1.0", "cmd_id": "corpus-007", "ts": NOW, "origin": "", "command": "Start"},
    {"schema_version": "1.0", "cmd_id": "short", "ts": NOW, "origin": "a@b", "command": "Start"},
    {"schema_version": "1.0", "cmd_id": "corpus-009", "ts": 12, "origin": "a@b", "command": "Start"},
    {"schema_version": "1.0", "cmd_id": "corpus-010", "ts": NOW, "origin": "a@b", "command": "Start", "x": 1},
    {"schema_version": "1.0", "cmd_id": "corpus-011", "ts": NOW, "origin": "a@b", "command": "AckReq", "value": 3.5},
    {"schema_version": "1.0", "cmd_id": "corpus-012", "ts": NOW, "origin": "a@b", "command": "Ack"},
    {"schema_version": "01.0", "cmd_id": "corpus-013", "ts": NOW, "origin": "a@b", "command": "Ack"},
    {"schema_version": "1.0", "cmd_id": "corpus-014", "ts": True, "origin": "a@b", "command": "Ack"},
]


@pytest.mark.parametrize("body", SCHEMA_CORPUS, ids=lambda b: str(b["cmd_id"]))
def test_gateway_rejects_whatever_schema_rejects(body: dict[str, Any], validators: dict[str, Any]) -> None:
    """Сообщение, которое не проходит command.schema.json, шлюз не пропускает к устройству."""
    gw = CommandGateway(TOPICS)
    schema_ok = validators["command"].is_valid(body)
    command = body["command"] if isinstance(body.get("command"), str) else "Start"
    topic = TOPICS.prefix + f"/P101/cmd/{command}"
    d = gw.check(topic, json.dumps(body).encode(), retained=False, now_ms=NOW)
    if not schema_ok:
        assert not d.passed, (body, d.reason)
    elif d.passed is False:
        # синтаксически верная команда может быть не разрешена устройству
        assert d.reason in ("not_whitelisted",), (body, d.reason)
