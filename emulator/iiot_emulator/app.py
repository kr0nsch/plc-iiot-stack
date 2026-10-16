"""Приложение эмулятора: цикл модели в реальном времени, OPC UA-сервер и MQTT.

Каждый такт (``tick_s`` реальных секунд):
1. записи клиентов OPC UA и команды MQTT, прошедшие шлюз, — в ``GVL_Hmi`` эмулятора
   (не больше одной команды MQTT на устройство за такт — так результат однозначен);
2. один цикл ПЛК и оценка результата команд (``eCmdResult``, ``uiCmdSeq``) → cmd_ack;
3. остальные циклы такта: ``time_factor · tick_s / step_s`` модельных шагов (дробная часть
   переносится на следующий такт);
4. изменившиеся значения — в узлы OPC UA; телеметрия и события тревог — в MQTT.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import queue
import time
from dataclasses import dataclass, field
from typing import Any

from . import __version__
from .alarms import AlarmEvent
from .commands import CommandGateway, Decision
from .config import Settings
from .devices import CmdResult, DeviceMode
from .emulator import CommandError, EmulatorConfig, KnsEmulator
from .schema import Topics, alarm_payload, default_topics
from .telemetry import NodeDiag, TelemetryTracker

log = logging.getLogger(__name__)

CMD_TIMEOUT_S = 3.0
MAX_STEPS_PER_TICK = 2000


@dataclass
class PendingCommand:
    decision: Decision
    seq_before: int
    deadline: float
    applied: bool = False
    extra: dict[str, object] = field(default_factory=dict)


def resolve_topics(settings: Settings) -> Topics:
    base = default_topics()
    m = settings.mqtt
    return Topics(
        site=m.site or base.site, area=m.area or base.area, unit=m.unit or base.unit, node=m.node or base.node
    )


class EmulatorApp:
    def __init__(self, settings: Settings, *, mqtt_client: Any = None) -> None:
        """``mqtt_client`` — готовый клиент paho (или его заменитель в тестах)."""
        self.s = settings
        sim = settings.sim
        self.emu = KnsEmulator(
            EmulatorConfig(
                seed=sim.seed,
                step_s=sim.step_s,
                start_hour=sim.start_hour,
                auto_faults=sim.auto_faults,
                auto_ack_s=sim.auto_ack_s,
            )
        )
        self.topics = resolve_topics(settings)
        self.diag = NodeDiag(start_monotonic=time.monotonic())
        self.tracker = TelemetryTracker(self.topics, period_s=settings.mqtt.period_s)
        self.gateway = CommandGateway(
            self.topics,
            max_age_s=settings.mqtt.cmd_max_age_s,
            rate_limit=settings.mqtt.cmd_rate_limit,
            rate_window_s=settings.mqtt.cmd_rate_window_s,
        )
        self.opcua = None
        self.mqtt = None
        self._pending: dict[str, PendingCommand] = {}
        self._alarm_last: dict[str, tuple[str, dict[str, Any]]] = {}
        self._start_ms = int(time.time() * 1000)
        self._carry = 0.0
        self._stop = asyncio.Event()
        self.ticks = 0
        if settings.mqtt.enable:
            from .mqtt_link import MqttLink

            self.mqtt = MqttLink(
                settings.mqtt, self.topics, self.gateway, self.diag, sw_version=__version__, client=mqtt_client
            )
            self.emu.listeners.append(self._on_alarm)
        if settings.opcua.enable:
            from .opcua_server import OpcUaMirror

            self.opcua = OpcUaMirror(self.emu, settings.opcua)

    # --- тревоги → MQTT -----------------------------------------------------------------------------
    def _on_alarm(self, ev: AlarmEvent) -> None:
        if self.mqtt is None:
            return
        a = ev.alarm
        suffix = a.code.split(".", 1)[1]
        payload = alarm_payload(
            int(time.time() * 1000),
            a.id,
            a.code,
            _prio(a.priority),
            int(ev.new_state),
            int(ev.old_state),
            int(ev.reason),
            ev.value,
        )
        topic = self.topics.alarm(a.device, suffix)
        self._alarm_last[a.code] = (topic, payload)
        self.mqtt.publish_alarm(topic, payload)

    def _alarm_snapshot(self) -> dict[str, tuple[str, dict[str, Any]]]:
        """Текущее состояние каждой тревоги: её последнее событие или «норма» с момента старта.

        После рождения узла (data_schema.md, раздел 6) публикуются все тревоги: retain у брокера
        тогда отражает состояние этого запуска, а не прошлого. Последнее событие повторяется с
        исходным ``ts`` — в InfluxDB это та же точка, а не новое событие.
        """
        out: dict[str, tuple[str, dict[str, Any]]] = {}
        for dev in self.emu.devs.values():
            for slot in dev.alarms.slots.values():
                a = slot.alarm
                last = self._alarm_last.get(a.code)
                if last is not None:
                    out[a.code] = last
                    continue
                state = int(slot.state)
                payload = alarm_payload(self._start_ms, a.id, a.code, _prio(a.priority), state, state, 2)  # Cleared
                out[a.code] = (self.topics.alarm(a.device, a.code.split(".", 1)[1]), payload)
        return out

    # --- команды MQTT -------------------------------------------------------------------------------
    def _take_commands(self) -> None:
        if self.mqtt is None:
            return
        deferred: list[Decision] = []
        while True:
            try:
                d = self.mqtt.commands.get_nowait()
            except queue.Empty:
                break
            if d.device in self._pending:
                deferred.append(d)  # у устройства уже есть команда в обработке
                continue
            self._apply_command(d)
        for d in deferred:
            self.mqtt.commands.put(d)

    def _apply_command(self, d: Decision) -> None:
        assert self.mqtt is not None and d.entry is not None
        dev = self.emu.devs.get(d.device)
        if dev is None:
            self._finish(d, "not_whitelisted")
            return
        if d.command in ("SpeedSp", "SubstValue"):
            # значения ФБ не квитирует (API 2.1): ok — после записи (data_schema.md, 5.1). Вне Manual
            # ФБ перезапишет поле слежением — так же, как при записи с HMI
            if dev.mode != DeviceMode.MANUAL:
                log.info("MQTT: %s/%s записано вне Manual — значение заменит слежение ФБ", d.device, d.command)
            try:
                self.emu.write_tag(d.entry.scada_tag, d.value)
            except CommandError:
                self._finish(d, "out_of_range")
                return
            self._finish(d, "ok")
            return
        try:
            self.emu.write_tag(d.entry.scada_tag, True if d.entry.value_type == "pulse" else d.value)
        except CommandError:
            self._finish(d, "invalid_payload")
            return
        self._pending[d.device] = PendingCommand(d, dev.cmd_seq, time.monotonic() + CMD_TIMEOUT_S, applied=True)

    def _evaluate_commands(self) -> None:
        now = time.monotonic()
        for device, pc in list(self._pending.items()):
            dev = self.emu.devs[device]
            if dev.cmd_seq != pc.seq_before:
                res = dev.cmd_result
                if res == CmdResult.ACCEPTED:
                    self._finish(pc.decision, "ok", int(res))
                else:
                    self._finish(pc.decision, "device_rejected", int(res))
                del self._pending[device]
            elif now >= pc.deadline:
                self._finish(pc.decision, "timeout")
                del self._pending[device]

    def _finish(self, d: Decision, reason: str, cmd_result: int | None = None) -> None:
        assert self.mqtt is not None
        if reason != "ok":
            self.gateway.note_device_result(False, reason)
        self.diag.cmd_accepted = self.gateway.stats.accepted
        self.diag.cmd_rejected = self.gateway.stats.rejected + self.gateway.stats.dropped
        self.mqtt.send_ack(d, reason, cmd_result)
        log.info("MQTT: %s/%s → %s %s", d.device, d.command, reason, cmd_result if cmd_result is not None else "")

    # --- такт ---------------------------------------------------------------------------------------
    async def tick(self, real_dt: float) -> None:
        if self.opcua is not None:
            self.opcua.apply_writes()
        self._take_commands()
        self._carry += self.s.sim.time_factor * real_dt / self.s.sim.step_s
        steps = int(self._carry)
        self._carry -= steps
        if steps > MAX_STEPS_PER_TICK:
            log.warning("эмулятор не успевает: %d шагов за такт, выполнено %d", steps, MAX_STEPS_PER_TICK)
            steps = MAX_STEPS_PER_TICK
        if self._pending and steps == 0:
            steps = 1  # команда должна быть обработана, даже если модель почти стоит
            self._carry -= 1
        if steps:
            self.emu.step(1)
            self._evaluate_commands()
            if steps > 1:
                self.emu.step(steps - 1)
        else:
            self._evaluate_commands()
        if self.opcua is not None:
            await self.opcua.publish(self.s.sim.time_factor)
        if self.mqtt is not None:
            force = self.mqtt.need_full_publish.is_set() and self.mqtt.connected.is_set()
            if force:
                self.mqtt.need_full_publish.clear()
                self.tracker.reset()
            msgs = self.tracker.collect(self.emu, int(time.time() * 1000), time.monotonic(), self.diag, force=force)
            self.mqtt.publish_telemetry(msgs)
            self.mqtt.flush_alarms()  # события, накопленные без связи, — по порядку
            if force:
                for code, (topic, payload) in self._alarm_snapshot().items():
                    if code not in self.mqtt.alarm_codes_since_connect:
                        self.mqtt.publish_json(topic, payload, retain=True)
        self.ticks += 1

    async def run(self, duration_s: float | None = None) -> None:
        if self.opcua is not None:
            await self.opcua.start()
        if self.mqtt is not None:
            self.mqtt.start()
        tick = self.s.sim.tick_s
        start = last = time.monotonic()
        log.info(
            "эмулятор КНС-1: seed=%d, ускорение ×%g, шаг %.2f с, старт %02.0f:00",
            self.s.sim.seed,
            self.s.sim.time_factor,
            self.s.sim.step_s,
            self.s.sim.start_hour,
        )
        try:
            while not self._stop.is_set():
                now = time.monotonic()
                await self.tick(now - last)
                last = now
                if duration_s is not None and now - start >= duration_s:
                    break
                elapsed = time.monotonic() - now
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._stop.wait(), timeout=max(0.0, tick - elapsed))
        finally:
            if self.mqtt is not None:
                self.mqtt.stop()
            if self.opcua is not None:
                await self.opcua.stop()

    def stop(self) -> None:
        self._stop.set()


def _prio(name: str) -> int:
    return {"None": 0, "Low": 1, "Medium": 2, "High": 3, "Critical": 4}.get(name, 0)
