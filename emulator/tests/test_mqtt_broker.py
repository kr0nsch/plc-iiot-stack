"""MQTT через настоящий клиент paho и тестовый брокер на 127.0.0.1.

Проверяется то, что заменитель клиента не покажет: логин на брокере, рождение и завещание с
retain, доставка команды подписчику и ответ, завещание при обрыве соединения.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

import pytest
from mini_broker import MiniBroker

from iiot_emulator.app import EmulatorApp
from iiot_emulator.config import MqttSettings, OpcUaSettings, Settings, SimSettings
from iiot_emulator.schema import default_topics

pytestmark = pytest.mark.network
TOPICS = default_topics()


def wait_for(cond: Callable[[], bool], timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


@pytest.fixture
def broker() -> Any:
    b = MiniBroker(users={"plc": "plc-secret", "operator": "op-secret"}).start()
    yield b
    b.stop()


def make_app(broker: MiniBroker, password: str = "plc-secret") -> EmulatorApp:
    settings = Settings(
        sim=SimSettings(time_factor=120.0, tick_s=0.05, auto_faults=False),
        opcua=OpcUaSettings(enable=False),
        mqtt=MqttSettings(host="127.0.0.1", port=broker.port, user="plc", password=password, period_s=60.0),
    )
    return EmulatorApp(settings)


async def run_app(app: EmulatorApp, seconds: float, during: Callable[[], Any] | None = None) -> None:
    task = asyncio.create_task(app.run())
    try:
        await asyncio.sleep(seconds / 2)
        if during is not None:
            await asyncio.to_thread(during)
        await asyncio.sleep(seconds / 2)
    finally:
        app.stop()
        await asyncio.wait_for(task, 10)


def payloads(broker: MiniBroker, topic: str) -> list[dict[str, Any]]:
    return [json.loads(m.payload) for m in broker.messages() if m.topic == topic]


def test_birth_telemetry_command_ack_and_shutdown(broker: MiniBroker, validators: dict[str, Any]) -> None:
    app = make_app(broker)

    def send_commands() -> None:
        assert wait_for(lambda: app.mqtt is not None and app.mqtt.connected.is_set())
        now = int(time.time() * 1000)
        for cmd_id, device, command in (
            ("e2e-stop-0001", "P101", "Stop"),
            ("e2e-oos-00001", "P102", "SetOos"),
        ):
            body = {"schema_version": "1.0", "cmd_id": cmd_id, "ts": now, "origin": "pytest@e2e", "command": command}
            broker.publish_from_test(f"{TOPICS.prefix}/{device}/cmd/{command}", json.dumps(body).encode())

    asyncio.run(run_app(app, 2.0, send_commands))

    status = payloads(broker, TOPICS.status())
    assert [s["reason"] for s in status] == ["birth", "shutdown"]
    assert (
        broker.retained[TOPICS.status()].payload
        and json.loads(broker.retained[TOPICS.status()].payload)["reason"] == "shutdown"
    )
    level = payloads(broker, TOPICS.telemetry("LT101", "level"))
    assert level and level[0]["unit"] == "m"
    for p in level:
        validators["telemetry"].validate(p)
    assert TOPICS.telemetry("P101", "running") in broker.retained
    acks = {p["cmd_id"]: p for p in payloads(broker, TOPICS.command_ack("P101", "Stop"))}
    acks.update({p["cmd_id"]: p for p in payloads(broker, TOPICS.command_ack("P102", "SetOos"))})
    assert acks["e2e-stop-0001"]["result"] == "accepted" and acks["e2e-stop-0001"]["cmd_result"] == "Accepted"
    assert acks["e2e-oos-00001"]["reason"] == "not_whitelisted"
    for a in acks.values():
        validators["command_ack"].validate(a)
    assert app.emu.read_tag("P101.Mode") == 2  # «Стоп» по MQTT перевёл насос в Manual
    assert not any(m.retain for m in broker.messages("/".join(TOPICS.command_ack("P101", "Stop").split("/")[:5])))


def test_last_will_on_connection_loss(broker: MiniBroker, validators: dict[str, Any]) -> None:
    app = make_app(broker)

    def kill() -> None:
        assert wait_for(lambda: app.mqtt is not None and app.mqtt.connected.is_set())
        broker.kill_client("kns-emulator")
        assert wait_for(lambda: any(p["reason"] == "lwt" for p in payloads(broker, TOPICS.status())))
        # paho переподключается сам: новое рождение
        assert wait_for(lambda: [p["reason"] for p in payloads(broker, TOPICS.status())].count("birth") >= 2, 8.0)

    asyncio.run(run_app(app, 3.0, kill))
    reasons = [p["reason"] for p in payloads(broker, TOPICS.status())]
    assert reasons[:3] == ["birth", "lwt", "birth"]
    for p in payloads(broker, TOPICS.status()):
        validators["status"].validate(p)
    assert app.diag.reconnects >= 1


def test_wrong_password_is_refused(broker: MiniBroker) -> None:
    app = make_app(broker, password="wrong")
    asyncio.run(run_app(app, 1.0))
    assert broker.rejected_logins >= 1
    assert not broker.messages(TOPICS.prefix)
