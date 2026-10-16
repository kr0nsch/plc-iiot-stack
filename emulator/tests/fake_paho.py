"""Заменитель клиента paho для тестов без сети: записывает публикации и подписки."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode


@dataclass
class Info:
    rc: int
    mid: int

    def wait_for_publish(self, timeout: float | None = None) -> None:
        return None


@dataclass
class Published:
    topic: str
    payload: bytes
    qos: int
    retain: bool

    @property
    def json(self) -> Any:
        return json.loads(self.payload)


@dataclass
class FakeClient:
    published: list[Published] = field(default_factory=list)
    subscriptions: list[tuple[str, int]] = field(default_factory=list)
    will: Published | None = None
    user: tuple[str, str | None] | None = None
    _mid: int = 0
    on_connect: Any = None
    on_disconnect: Any = None
    on_message: Any = None
    on_publish: Any = None

    def username_pw_set(self, user: str, password: str | None = None) -> None:
        self.user = (user, password)

    def tls_set(self, **kw: Any) -> None:
        pass

    def tls_insecure_set(self, v: bool) -> None:
        pass

    def will_set(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> None:
        self.will = Published(topic, payload, qos, retain)

    def reconnect_delay_set(self, min_delay: int = 1, max_delay: int = 120) -> None:
        pass

    def max_inflight_messages_set(self, n: int) -> None:
        pass

    def connect_async(self, host: str, port: int, keepalive: int = 60) -> None:
        pass

    def loop_start(self) -> None:
        pass

    def loop_stop(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def subscribe(self, topic: str, qos: int = 0) -> tuple[int, int]:
        self.subscriptions.append((topic, qos))
        return 0, 1

    def publish(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> Info:
        self._mid += 1
        self.published.append(Published(topic, payload, qos, retain))
        if self.on_publish is not None:
            self.on_publish(self, None, self._mid, ReasonCode(PacketTypes.PUBACK, "Success"), None)
        return Info(mqtt.MQTT_ERR_SUCCESS, self._mid)

    # --- управление из теста ----------------------------------------------------------------------
    def connect_now(self) -> None:
        self.on_connect(self, None, None, ReasonCode(PacketTypes.CONNACK, "Success"), None)

    def deliver(self, topic: str, payload: bytes, retain: bool = False) -> None:
        msg = mqtt.MQTTMessage(topic=topic.encode())
        msg.payload = payload
        msg.retain = retain
        self.on_message(self, None, msg)

    def take(self) -> list[Published]:
        out, self.published = self.published, []
        return out
