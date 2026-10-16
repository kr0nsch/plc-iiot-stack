"""MQTT эмулятора на paho-mqtt (API обратных вызовов версии 2).

- Подключение с логином и паролем, TLS по флагу; автоматическое переподключение.
- Завещание (LWT): ``.../PLC1/status/connection`` = offline/lwt, retain; после подключения —
  рождение online/birth (retain) и полная публикация всех метрик; при штатной остановке —
  offline/shutdown.
- Телеметрия и события тревог — QoS 1, retain (topics.json). Пока связи нет, телеметрия не
  копится (после подключения уйдёт полный срез), события тревог ждут в ограниченной очереди.
- Команды: подписка ``<prefix>/+/cmd/+`` (QoS 1); решение шлюза (``commands.py``) — в потоке
  paho, отказ шлюза отвечается сразу, прошедшая проверку команда уходит в цикл эмулятора.
"""

from __future__ import annotations

import contextlib
import logging
import queue
import ssl
import threading
import time
from collections import deque
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

from .commands import CommandGateway, Decision
from .config import MqttSettings
from .schema import Topics, ack_payload, dumps, status_payload
from .telemetry import NodeDiag

log = logging.getLogger(__name__)

ALARM_QUEUE_MAX = 1000


def now_ms() -> int:
    return int(time.time() * 1000)


class MqttLink:
    def __init__(
        self,
        settings: MqttSettings,
        topics: Topics,
        gateway: CommandGateway,
        diag: NodeDiag,
        *,
        sw_version: str = "",
        client: mqtt.Client | None = None,
    ) -> None:
        self.s = settings
        self.topics = topics
        self.gateway = gateway
        self.diag = diag
        self.sw_version = sw_version
        self.connected = threading.Event()
        self.need_full_publish = threading.Event()
        self.commands: queue.Queue[Decision] = queue.Queue()
        self.published: deque[tuple[str, dict[str, Any], bool]] = deque(maxlen=0)  # журнал для тестов
        self._alarm_backlog: deque[tuple[str, dict[str, Any]]] = deque()
        self._inflight: set[int] = set()
        self.alarm_codes_since_connect: set[str] = set()
        self._lock = threading.Lock()
        self._connects = 0
        self._connect_ts = now_ms()
        self.client = client or mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=settings.client_id,
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )
        c = self.client
        if settings.user:
            c.username_pw_set(settings.user, settings.password or None)
        if settings.tls:
            c.tls_set(
                ca_certs=settings.ca_file or None,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            if settings.tls_insecure:
                c.tls_insecure_set(True)
        self._set_will()
        c.reconnect_delay_set(min_delay=1, max_delay=30)
        c.max_inflight_messages_set(50)
        c.on_connect = self._on_connect
        c.on_disconnect = self._on_disconnect
        c.on_message = self._on_message
        c.on_publish = self._on_publish

    # --- жизненный цикл -----------------------------------------------------------------------------
    def _set_will(self) -> None:
        self._connect_ts = now_ms()
        will = status_payload(self._connect_ts, self.topics.node, False, "lwt", sw_version=self.sw_version)
        self.client.will_set(self.topics.status(), dumps(will), qos=1, retain=True)

    def start(self) -> None:
        log.info("MQTT: подключение к %s:%d (TLS: %s)", self.s.host, self.s.port, self.s.tls)
        self.client.connect_async(self.s.host, self.s.port, keepalive=self.s.keepalive_s)
        self.client.loop_start()

    def stop(self, timeout_s: float = 3.0) -> None:
        if self.connected.is_set():
            payload = status_payload(now_ms(), self.topics.node, False, "shutdown", sw_version=self.sw_version)
            info = self.client.publish(self.topics.status(), dumps(payload), qos=1, retain=True)
            with contextlib.suppress(RuntimeError, ValueError):
                info.wait_for_publish(timeout=timeout_s)
        self.client.disconnect()
        self.client.loop_stop()

    def _on_connect(
        self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: ReasonCode, properties: Properties | None
    ) -> None:
        if reason_code.is_failure:
            log.error("MQTT: брокер отказал в подключении: %s", reason_code)
            return
        self._connects += 1
        if self._connects > 1:
            self.diag.reconnects += 1
        birth = status_payload(
            now_ms(), self.topics.node, True, "birth", sw_version=self.sw_version, period_ms=int(self.s.period_s * 1000)
        )
        client.publish(self.topics.status(), dumps(birth), qos=1, retain=True)
        client.subscribe(self.topics.command_filter(), qos=1)
        self.alarm_codes_since_connect = set()
        self.connected.set()
        self.need_full_publish.set()
        log.info("MQTT: подключено, подписка %s", self.topics.command_filter())

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: ReasonCode,
        properties: Properties | None,
    ) -> None:
        self.connected.clear()
        self._set_will()  # время в завещании — время следующего подключения
        if reason_code.is_failure:
            log.warning("MQTT: связь потеряна (%s), переподключение", reason_code)

    def _on_publish(
        self, client: mqtt.Client, userdata: Any, mid: int, reason_code: ReasonCode, properties: Properties | None
    ) -> None:
        with self._lock:
            self._inflight.discard(mid)
            self.diag.queue = len(self._inflight) + len(self._alarm_backlog)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        d = self.gateway.check(msg.topic, msg.payload, retained=bool(msg.retain), now_ms=now_ms())
        if d.cmd_id is None:
            log.warning("MQTT: команда без ответа (%s: %s) в %s", d.reason, d.detail, msg.topic)
            self.diag.cmd_rejected = self.gateway.stats.rejected + self.gateway.stats.dropped
            return
        if d.passed:
            self.commands.put(d)
        else:
            log.info("MQTT: %s/%s отклонена шлюзом: %s %s", d.device, d.command, d.reason, d.detail)
            self.send_ack(d, d.reason)
        self.diag.cmd_accepted = self.gateway.stats.accepted
        self.diag.cmd_rejected = self.gateway.stats.rejected + self.gateway.stats.dropped

    # --- публикация ---------------------------------------------------------------------------------
    def publish_json(self, topic: str, payload: dict[str, Any], *, retain: bool, qos: int = 1) -> bool:
        info = self.client.publish(topic, dumps(payload), qos=qos, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            self.diag.dropped += 1
            return False
        with self._lock:
            if qos > 0:
                self._inflight.add(info.mid)
            self.diag.queue = len(self._inflight) + len(self._alarm_backlog)
        if self.published.maxlen:
            self.published.append((topic, payload, retain))
        return True

    def publish_telemetry(self, messages: list[tuple[str, dict[str, Any]]]) -> int:
        if not self.connected.is_set():
            return 0
        return sum(1 for topic, payload in messages if self.publish_json(topic, payload, retain=True))

    def publish_alarm(self, topic: str, payload: dict[str, Any]) -> None:
        """Событие тревоги: без связи — в очередь (не больше ALARM_QUEUE_MAX), потом по порядку."""
        with self._lock:
            self._alarm_backlog.append((topic, payload))
            while len(self._alarm_backlog) > ALARM_QUEUE_MAX:
                self._alarm_backlog.popleft()
                self.diag.dropped += 1
        self.flush_alarms()

    def flush_alarms(self) -> None:
        while self.connected.is_set():
            with self._lock:
                if not self._alarm_backlog:
                    break
                topic, payload = self._alarm_backlog.popleft()
            if not self.publish_json(topic, payload, retain=True):
                break
            self.alarm_codes_since_connect.add(str(payload.get("code", "")))

    def send_ack(self, d: Decision, reason: str, cmd_result: int | None = None) -> None:
        assert d.cmd_id is not None
        payload = ack_payload(now_ms(), d.cmd_id, d.command, reason, cmd_result)
        self.publish_json(self.topics.command_ack(d.device, d.command), payload, retain=False)
