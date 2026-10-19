"""Каждый вид сообщения эмулятора проходит JSON Schema стенда (schema/*.schema.json).

Сообщения собираются с настоящего кода публикации (``EmulatorApp`` + ``MqttLink``) на
заменителе клиента paho: телеметрия (полный срез и изменения, все виды качества), события
тревог (все причины, которые даёт модель: появление, снятие, квитирование, shelve, OOS),
ответы на команды (все причины отказа), состояние узла (рождение, завещание, штатная остановка).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections import Counter
from typing import Any

import pytest
from fake_paho import FakeClient, Published

from iiot_emulator.app import EmulatorApp
from iiot_emulator.config import MqttSettings, OpcUaSettings, Settings, SimSettings
from iiot_emulator.devices import AnalogInput
from iiot_emulator.schema import ACK_REASONS, default_topics

TOPICS = default_topics()


def classify(topic: str, patterns: dict[str, re.Pattern[str]]) -> str:
    matched = [name for name, rx in patterns.items() if rx.match(topic)]
    # telemetry и alarm различаются числом уровней; status/cmd_ack — по зарезервированному слову
    assert len(matched) == 1, (topic, matched)
    return matched[0]


def make_app(**sim: Any) -> tuple[EmulatorApp, FakeClient]:
    client = FakeClient()
    settings = Settings(
        sim=SimSettings(time_factor=sim.pop("time_factor", 600.0), auto_faults=False, **sim),
        opcua=OpcUaSettings(enable=False),
        mqtt=MqttSettings(user="plc", password="x", period_s=60.0),
    )
    app = EmulatorApp(settings, mqtt_client=client)
    return app, client


def run_ticks(app: EmulatorApp, n: int, dt: float = 0.25) -> None:
    async def go() -> None:
        for _ in range(n):
            await app.tick(dt)

    asyncio.run(go())


def command(device: str, name: str, cmd_id: str, value: float | None = None, **over: Any) -> tuple[str, bytes]:
    body: dict[str, Any] = {
        "schema_version": "1.0",
        "cmd_id": cmd_id,
        "ts": int(time.time() * 1000),
        "origin": "pytest@emulator",
        "command": name,
    }
    if value is not None:
        body["value"] = value
    body.update(over)
    return f"{TOPICS.prefix}/{device}/cmd/{name}", json.dumps(body).encode()


@pytest.fixture(scope="module")
def traffic() -> tuple[list[Published], FakeClient, EmulatorApp]:
    """Насыщенный прогон: отказы, ливень, команды MQTT всех исходов."""
    app, client = make_app()
    assert client.will is not None
    client.connect_now()
    emu = app.emu
    emu.plant.force_storm(450.0, 2.0)
    run_ticks(app, 8)  # полный срез после рождения
    for fault in ("p1_vfd_trip", "lt101_wire_break", "p2_comm_loss", "door_open", "h2s_spike", "p3_clog"):
        emu.inject(fault)
    run_ticks(app, 40)  # 40 тактов × 0,25 с × 600 = 6000 модельных секунд
    for fault in ("lt101_wire_break", "p2_comm_loss", "door_open", "p1_vfd_trip"):
        emu.inject(fault, False)
    # shelve и снятие, вывод из работы и возврат — через команды HMI
    emu.write_tag("ZS404.Cmd.ShelveReq", 1)
    emu.write_tag("AT401.Cmd.SetOos", True)
    emu.write_tag("PT201.Cmd.SetManual", True)  # подмена значения: качество uncertain
    run_ticks(app, 4)
    emu.write_tag("ZS404.Cmd.UnshelveReq", 1)
    emu.write_tag("AT401.Cmd.SetAuto", True)
    emu.write_tag("PT201.Cmd.SetAuto", True)
    run_ticks(app, 4)
    # команды MQTT: принятые, отклонённые устройством и шлюзом
    deliveries = [
        command("P101", "Reset", "cmd-reset-0001"),
        command("P102", "Start", "cmd-start-0001"),  # в Auto → device_rejected RejectedMode
        command("P101", "SetOos", "cmd-oos-00001"),  # нет в белом списке
        command("P103", "SpeedSp", "cmd-speed-0001", 140.0),  # вне диапазона
        command("P103", "SpeedSp", "cmd-speed-0002", 70.0),  # значение: ok после записи
        command("P101", "Ack", "cmd-ack-000001", schema_version="2.0"),
        command("P101", "Ack", "cmd-ack-000002", ts=1_600_000_000_000),  # просрочена
        command("P101", "Ack", "cmd-reset-0001"),  # повтор cmd_id
        command("P101", "Ack", "cmd-ack-000003", value=1),  # значение у импульсной команды
        command("KNS1", "SetStepped", "cmd-kns-stepped1"),  # станция: GVL_Station.stStationCmd
        command("LIC101", "SetManual", "cmd-lic-manual01"),  # регулятор уровня: stLIC101Cmd.stCommon
        command("KNS1", "ExportLog", "cmd-kns-export01"),  # поле stStationCmd, но не в белом списке
    ]
    for topic, payload in deliveries:
        client.deliver(topic, payload)
    topic, payload = command("P102", "Stop", "cmd-retained-1")
    client.deliver(topic, payload, retain=True)
    topic, _ = command("P102", "Ack", "cmd-mismatch-1")
    client.deliver(topic, command("P102", "Reset", "cmd-mismatch-1")[1])
    run_ticks(app, 6)
    # штатная остановка
    app.mqtt.stop()  # type: ignore[union-attr]
    return client.published, client, app


def test_every_message_matches_schema(
    traffic: tuple[list[Published], FakeClient, EmulatorApp],
    validators: dict[str, Any],
    topic_patterns: dict[str, re.Pattern[str]],
) -> None:
    published, client, _ = traffic
    kinds: Counter[str] = Counter()
    assert client.will is not None
    for msg in [*published, client.will]:
        kind = classify(msg.topic, topic_patterns)
        validators[kind].validate(msg.json)
        kinds[kind] += 1
        if kind in ("telemetry", "alarm", "status"):
            assert msg.retain and msg.qos == 1, msg.topic
        else:
            assert not msg.retain and msg.qos == 1, msg.topic
    assert set(kinds) == {"telemetry", "alarm", "command_ack", "status"}


def test_telemetry_covers_catalog_and_qualities(traffic: tuple[list[Published], FakeClient, EmulatorApp]) -> None:
    from iiot_emulator.schema import telemetry_catalog

    published, _, _ = traffic
    tele = [
        m for m in published if "/alarm/" not in m.topic and "/cmd_ack/" not in m.topic and "/status/" not in m.topic
    ]
    topics = {m.topic for m in tele}
    expected = {TOPICS.telemetry(m.device, m.metric) for m in telemetry_catalog()}
    assert topics == expected
    qualities = Counter(m.json["quality"] for m in tele)
    assert {"good", "bad", "uncertain"} <= set(qualities), qualities
    level = [m.json for m in tele if m.topic.endswith("/LT101/level")]
    assert any(p["quality"] == "bad" for p in level)  # обрыв линии LT101
    assert all(isinstance(p["value"], int | float) for p in level)


def test_alarm_events_cover_reasons(
    traffic: tuple[list[Published], FakeClient, EmulatorApp], topic_patterns: dict[str, re.Pattern[str]]
) -> None:
    published, _, app = traffic
    alarms = [m for m in published if classify(m.topic, topic_patterns) == "alarm"]
    reasons = Counter(m.json["reason"] for m in alarms)
    assert {"Activated", "Cleared", "Acked", "Shelved", "Unshelved", "OosOn", "OosOff"} <= set(reasons), reasons
    for m in alarms:
        device, suffix = m.topic.split("/")[3], m.topic.split("/")[5]
        assert m.json["code"] == f"{device}.{suffix}"
    codes = {m.json["code"] for m in alarms if m.json["reason"] == "Activated"}
    assert {"P101.EXT", "LT101.FAIL", "P102.COM", "ZS404.ALM"} <= codes, codes
    # после рождения — текущее состояние каждой тревоги, затем каждое событие модели
    n_slots = sum(len(d.alarms.slots) for d in app.emu.devs.values())
    assert n_slots == 88  # 75 тревог устройств и 13 тревог станции KNS1.*
    assert len(alarms) == n_slots + len(app.emu.events)
    snapshot = alarms[:n_slots]
    assert len({m.json["code"] for m in snapshot}) == n_slots
    assert all(m.json["state"] == "Normal" for m in snapshot)


def test_alarm_snapshot_after_reconnect_repeats_last_event() -> None:
    """Повторное рождение публикует последнее событие тревоги с исходным ts (та же точка в БД)."""
    app, client = make_app()
    client.connect_now()
    run_ticks(app, 2)
    app.emu.inject("door_open")
    run_ticks(app, 4)
    events = [m.json for m in client.take() if m.topic.endswith("/ZS404/alarm/ALM")]
    last = events[-1]
    assert last["reason"] in ("Activated", "Acked")
    assert app.mqtt is not None
    app.mqtt.connected.clear()
    client.connect_now()  # переподключение: рождение и полный срез
    run_ticks(app, 1)
    again = [m.json for m in client.take() if m.topic.endswith("/ZS404/alarm/ALM")]
    assert again == [last]


def test_command_acks(traffic: tuple[list[Published], FakeClient, EmulatorApp]) -> None:
    published, _, _ = traffic
    acks = {m.json["cmd_id"] + ":" + m.json["command"]: m.json for m in published if "/cmd_ack/" in m.topic}
    assert acks["cmd-reset-0001:Reset"]["result"] == "accepted"
    assert acks["cmd-reset-0001:Reset"]["cmd_result"] == "Accepted"
    assert acks["cmd-start-0001:Start"]["reason"] == "device_rejected"
    assert acks["cmd-start-0001:Start"]["cmd_result"] == "RejectedMode"
    assert acks["cmd-oos-00001:SetOos"]["reason"] == "not_whitelisted"
    assert acks["cmd-speed-0001:SpeedSp"]["reason"] == "out_of_range"
    assert acks["cmd-speed-0002:SpeedSp"]["reason"] == "ok"
    assert "cmd_result" not in acks["cmd-speed-0002:SpeedSp"]  # значения ФБ не квитирует
    assert acks["cmd-ack-000001:Ack"]["reason"] == "unsupported_version"
    assert acks["cmd-ack-000002:Ack"]["reason"] == "expired"
    assert acks["cmd-reset-0001:Ack"]["reason"] == "duplicate"
    assert acks["cmd-ack-000003:Ack"]["reason"] == "invalid_payload"
    assert acks["cmd-retained-1:Stop"]["reason"] == "retained"
    assert acks["cmd-mismatch-1:Ack"]["reason"] == "topic_mismatch"
    assert acks["cmd-kns-stepped1:SetStepped"]["reason"] == "ok"
    assert acks["cmd-kns-stepped1:SetStepped"]["cmd_result"] == "Accepted"
    assert acks["cmd-lic-manual01:SetManual"]["reason"] == "ok"
    assert acks["cmd-kns-export01:ExportLog"]["reason"] == "invalid_payload"  # имени нет в command.schema.json
    for a in acks.values():
        assert a["reason"] in ACK_REASONS


def test_birth_lwt_shutdown(traffic: tuple[list[Published], FakeClient, EmulatorApp]) -> None:
    published, client, _ = traffic
    status = [m.json for m in published if m.topic == TOPICS.status()]
    assert status[0]["state"] == "online" and status[0]["reason"] == "birth"
    assert status[0]["source"] == "emulator" and status[0]["period_ms"] == 60000
    assert status[-1]["state"] == "offline" and status[-1]["reason"] == "shutdown"
    assert client.will is not None and client.will.topic == TOPICS.status()
    assert client.will.json["reason"] == "lwt" and client.will.retain
    assert client.subscriptions == [(TOPICS.command_filter(), 1)]


def test_diag_metrics_count_commands(traffic: tuple[list[Published], FakeClient, EmulatorApp]) -> None:
    published, _, app = traffic
    assert app.diag.cmd_accepted == 4  # Reset, SpeedSp, команды станции и LIC101
    assert app.diag.cmd_rejected == 10
    last = {m.topic: m.json for m in published if "/PLC1/" in m.topic and "/status/" not in m.topic}
    assert set(last) >= {TOPICS.telemetry("PLC1", k) for k in ("uptime", "cmd_accepted", "cmd_rejected")}


def test_schema_examples_are_valid(validators: dict[str, Any], topic_patterns: dict[str, re.Pattern[str]]) -> None:
    """Примеры schema/examples проходят свои схемы (проверка самих примеров и классификатора)."""
    from conftest import SCHEMA_DIR

    files = sorted((SCHEMA_DIR / "examples").glob("*.json"))
    assert files
    for f in files:
        ex = json.loads(f.read_text(encoding="utf-8"))
        kind = classify(ex["topic"], topic_patterns)
        validators[kind].validate(ex["payload"])


def test_ack_reasons_match_schema() -> None:
    from conftest import load_schema

    schema = load_schema("command_ack.schema.json")
    assert tuple(schema["properties"]["reason"]["enum"]) == ACK_REASONS


def test_deadband_suppresses_small_changes() -> None:
    """Повторный сбор без изменений ничего не публикует, кроме метрик, ушедших за deadband."""
    from iiot_emulator.telemetry import NodeDiag, TelemetryTracker

    app, _ = make_app(time_factor=0.0)
    tracker = TelemetryTracker(TOPICS, period_s=3600.0)
    diag = NodeDiag(start_monotonic=0.0)
    first = tracker.collect(app.emu, 1_792_137_600_000, 1.0, diag)
    second = tracker.collect(app.emu, 1_792_137_600_100, 2.0, diag)
    assert len(first) == len(tracker.catalog)
    assert second == []
    lt = app.emu.devs["LT101"]
    assert isinstance(lt, AnalogInput)
    lt.value = 0.0  # имитация изменения образа без шага модели
    lt._sts_dirty = True
    third = tracker.collect(app.emu, 1_792_137_600_200, 3.0, diag)
    assert [t for t, _ in third] == [TOPICS.telemetry("LT101", "level")]


@pytest.mark.parametrize(
    ("new", "last", "deadband", "expected"),
    [
        (2.5, 2.0, 0.5, False),  # ровно на зону — не публикуется (строго «больше», как в ПЛК)
        (2.5000001, 2.0, 0.5, True),
        (102.0, 100.0, 2.0, False),
        (1.0, 1.0, None, False),
        (1.0, 0.0, None, True),  # без зоны — любое изменение
        (1.0, 0.0, 0.0, True),
        (float("nan"), 1.0, 0.5, True),  # число ↔ NaN — изменение
        (float("nan"), float("inf"), 0.5, False),  # два неконечных — нет
    ],
)
def test_deadband_matches_plc_function(new: float, last: float, deadband: float | None, expected: bool) -> None:
    """Та же таблица истинности, что у F_IiotDeadbandExceeded (тест coUnit DeadbandIsStrictlyGreater)."""
    from iiot_emulator.telemetry import deadband_exceeded

    assert deadband_exceeded(new, last, deadband) is expected
