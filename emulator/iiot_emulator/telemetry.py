"""Выбор сообщений телеметрии: по изменению с зоной нечувствительности и периодически.

Логика та же, что у публикатора ПЛК: метрика публикуется, если
- её ещё не публиковали с последнего подключения (рождение узла);
- изменилось качество;
- значение ушло от последнего опубликованного больше чем на deadband (у метрик без deadband —
  любое изменение);
- настал период контрольной публикации (все метрики сразу).

Модуль не зависит от paho: на вход — образ ПЛК, на выход — пары (топик, тело).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .devices import AnalogInput, DigitalInput, MotorVfd
from .emulator import KnsEmulator
from .schema import Metric, Topics, quality_from_ne107, telemetry_catalog, telemetry_payload
from .station_devices import StationDevice

# Метрики ПЧ, которые ПЛК читает по Modbus: при потере связи значение замирает (quality = bad)
VFD_COMM_METRICS = frozenset({"speed", "vfd_fault_code"})
MIN_INTERVAL_S = 1.0  # не чаще одного сообщения в секунду на метрику (data_schema.md, 3.3)


@dataclass
class NodeDiag:
    """Диагностика узла (метрики PLC1 каталога)."""

    start_monotonic: float = 0.0
    reconnects: int = 0
    queue: int = 0
    dropped: int = 0
    cmd_accepted: int = 0
    cmd_rejected: int = 0


def deadband_exceeded(new: float, last: float, deadband: float | None) -> bool:
    """Изменение вне зоны нечувствительности — как ``F_IiotDeadbandExceeded`` ПЛК.

    Строго «больше» зоны (data_schema.md, 3.3); зона не задана, не больше 0 или не число — любое
    изменение; переход между числом и NaN/бесконечностью — изменение, между двумя неконечными — нет.
    """
    new_finite, last_finite = math.isfinite(new), math.isfinite(last)
    if not new_finite or not last_finite:
        return new_finite != last_finite
    diff = abs(new - last)
    if deadband is None or not math.isfinite(deadband) or deadband <= 0.0:
        return diff > 0.0
    return diff > deadband


def _number(value: Any, kind: str) -> float | int:
    if isinstance(value, bool):
        return int(value)
    if kind in ("analog", "counter") and isinstance(value, float):
        return round(value, 4)
    if isinstance(value, float) and value.is_integer() and kind in ("enum", "integer", "discrete"):
        return int(value)
    return value  # type: ignore[no-any-return]


class TelemetryTracker:
    def __init__(self, topics: Topics, catalog: tuple[Metric, ...] | None = None, period_s: float = 60.0) -> None:
        self.topics = topics
        self.catalog = catalog if catalog is not None else telemetry_catalog()
        self.period_s = period_s
        self._last: dict[str, tuple[float | int, str, float]] = {}  # значение, качество, время
        self._last_period: float | None = None

    def reset(self) -> None:
        """После переподключения: опубликовать всё заново."""
        self._last.clear()
        self._last_period = None

    def quality(self, emu: KnsEmulator, m: Metric) -> str:
        """Достоверность метрики — по устройству-источнику (data_schema.md, 3.2)."""
        dev = emu.devs.get(m.device)
        if dev is None or isinstance(dev, StationDevice):
            return "good"  # диагностика узла PLC1, сигналы без ФБ (K1), расчётные значения станции KNS1
        if isinstance(dev, MotorVfd) and m.metric in VFD_COMM_METRICS and dev.comm_loss:
            return "bad"
        valid = dev.valid if isinstance(dev, AnalogInput | DigitalInput) else True
        return quality_from_ne107(int(dev.ne107), valid)

    def value(self, emu: KnsEmulator, image: dict[str, Any], m: Metric, diag: NodeDiag, now_s: float) -> float | int:
        if m.scada_tag:
            value = image[m.scada_tag]
            if m.invert:
                value = not bool(value)  # K1: реле под напряжением в норме, метрика — «общая авария»
            return _number(value, m.kind)
        return {
            "uptime": int(max(0.0, now_s - diag.start_monotonic)),
            "reconnects": diag.reconnects,
            "queue": diag.queue,
            "dropped": diag.dropped,
            "cmd_accepted": diag.cmd_accepted,
            "cmd_rejected": diag.cmd_rejected,
        }.get(m.metric, 0)

    def collect(
        self, emu: KnsEmulator, ts_ms: int, now_s: float, diag: NodeDiag, *, force: bool = False
    ) -> list[tuple[str, dict[str, Any]]]:
        """Сообщения, которые нужно опубликовать сейчас."""
        image = emu.image()
        periodic = force or self._last_period is None or (now_s - self._last_period) >= self.period_s
        if periodic:
            self._last_period = now_s
        out: list[tuple[str, dict[str, Any]]] = []
        for m in self.catalog:
            topic = self.topics.telemetry(m.device, m.metric)
            value = self.value(emu, image, m, diag, now_s)
            quality = self.quality(emu, m)
            last = self._last.get(topic)
            send = periodic or last is None or last[1] != quality
            if not send and last is not None and now_s - last[2] >= MIN_INTERVAL_S:
                send = deadband_exceeded(float(value), float(last[0]), m.deadband)
            if m.metric == "uptime" and not periodic:
                send = False  # время работы — только с контрольной публикацией
            if send:
                self._last[topic] = (value, quality, now_s)
                out.append((topic, telemetry_payload(ts_ms, value, quality, m.unit)))
        return out
