"""Тревоги устройства: упрощённая модель FB_Alarm библиотеки plc-process-lib (API 4.4, 10).

Слот тревоги живёт по ISA-18.2 в объёме, который нужен SCADA и дашбордам: задержка появления,
квитирование, отложенные (shelve) и выведенные из работы вместе с устройством тревоги. Каждое
изменение состояния — событие (``AlarmEvent``) для журнала и MQTT.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from .tagmodel import AlarmDef


class AlarmState(IntEnum):
    """E_AlarmState (API 4.1)."""

    NORMAL = 0
    ACTIVE_UNACK = 1
    ACTIVE_ACK = 2
    RTN_UNACK = 3
    SHELVED = 4
    SUPPRESSED_BY_DESIGN = 5
    OUT_OF_SERVICE = 6


class AlarmPriority(IntEnum):
    """E_AlarmPriority (API 4.1)."""

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def parse(cls, text: str) -> AlarmPriority:
        return cls[text.strip().upper()] if text.strip() else cls.NONE


class AlarmReason(IntEnum):
    """E_AlarmEventReason (API 4.1)."""

    NONE = 0
    ACTIVATED = 1
    CLEARED = 2
    ACKED = 3
    SHELVED = 4
    UNSHELVED = 5
    SHELVE_EXPIRED = 6
    SUPPRESSED = 7
    UNSUPPRESSED = 8
    OOS_ON = 9
    OOS_OFF = 10


@dataclass(frozen=True)
class AlarmEvent:
    """Событие тревоги (аналог ST_AlarmEvent; время — модельное, в секундах)."""

    alarm: AlarmDef
    old_state: AlarmState
    new_state: AlarmState
    reason: AlarmReason
    sim_time_s: float
    value: float | None

    @property
    def active(self) -> bool:
        return self.new_state in (AlarmState.ACTIVE_UNACK, AlarmState.ACTIVE_ACK)

    @property
    def acked(self) -> bool:
        return self.new_state in (AlarmState.NORMAL, AlarmState.ACTIVE_ACK)


EventSink = Callable[[AlarmEvent], None]

SHELVE_MAX_S = 8 * 3600.0  # ST_AlarmCfg.tShelveMax по умолчанию T#8H


class AlarmSlot:
    """Один слот тревоги устройства."""

    def __init__(self, alarm: AlarmDef) -> None:
        self.alarm = alarm
        self.priority = AlarmPriority.parse(alarm.priority)
        self.state = AlarmState.NORMAL
        self.cond_since: float | None = None  # момент появления условия (для задержки)
        self.active = False  # условие после задержки
        self.unack = False
        self.shelved_until: float | None = None
        self.oos = False

    def _set(self, new: AlarmState, reason: AlarmReason, t: float, value: float | None, sink: EventSink) -> None:
        if new == self.state:
            return
        old, self.state = self.state, new
        sink(AlarmEvent(self.alarm, old, new, reason, t, value))

    def _derived_state(self) -> AlarmState:
        if self.oos:
            return AlarmState.OUT_OF_SERVICE
        if self.shelved_until is not None:
            return AlarmState.SHELVED
        if self.active:
            return AlarmState.ACTIVE_UNACK if self.unack else AlarmState.ACTIVE_ACK
        return AlarmState.RTN_UNACK if self.unack else AlarmState.NORMAL

    def update(self, cond: bool, t: float, value: float | None, sink: EventSink) -> None:
        """Шаг слота: условие (до задержки) → состояние и события."""
        if self.oos:
            self.cond_since = None
            self.active = False
            return
        if self.shelved_until is not None and t >= self.shelved_until:
            self.shelved_until = None
            self.unack = self.active
            self._set(self._derived_state(), AlarmReason.SHELVE_EXPIRED, t, value, sink)
        if cond:
            if self.cond_since is None:
                self.cond_since = t
            delayed = (t - self.cond_since) >= self.alarm.delay_s - 1e-9
        else:
            self.cond_since = None
            delayed = False
        if delayed and not self.active:
            self.active = True
            if self.shelved_until is None:
                self.unack = True
            self._set(self._derived_state(), AlarmReason.ACTIVATED, t, value, sink)
        elif not delayed and self.active:
            self.active = False
            self._set(self._derived_state(), AlarmReason.CLEARED, t, value, sink)

    def ack(self, t: float, value: float | None, sink: EventSink) -> bool:
        if not self.unack:
            return False
        self.unack = False
        self._set(self._derived_state(), AlarmReason.ACKED, t, value, sink)
        return True

    def shelve(self, t: float, value: float | None, sink: EventSink) -> bool:
        if self.oos or self.shelved_until is not None:
            return False
        self.shelved_until = t + SHELVE_MAX_S
        self.unack = False
        self._set(AlarmState.SHELVED, AlarmReason.SHELVED, t, value, sink)
        return True

    def unshelve(self, t: float, value: float | None, sink: EventSink) -> bool:
        if self.shelved_until is None:
            return False
        self.shelved_until = None
        self.unack = self.active
        self._set(self._derived_state(), AlarmReason.UNSHELVED, t, value, sink)
        return True

    def set_oos(self, oos: bool, t: float, sink: EventSink) -> None:
        if oos == self.oos:
            return
        self.oos = oos
        if oos:
            self.active = False
            self.unack = False
            self.cond_since = None
            self.shelved_until = None
            self._set(AlarmState.OUT_OF_SERVICE, AlarmReason.OOS_ON, t, None, sink)
        else:
            self._set(self._derived_state(), AlarmReason.OOS_OFF, t, None, sink)


class AlarmBlock:
    """Тревоги одного устройства: слоты по scada_alarms.csv и слова wAlm* для Sts."""

    def __init__(self, alarms: list[AlarmDef], sink: EventSink) -> None:
        self.slots: dict[int, AlarmSlot] = {a.slot: AlarmSlot(a) for a in alarms}
        self._sink = sink

    def update(self, conds: dict[int, bool], t: float, values: dict[int, float | None] | None = None) -> None:
        for slot_no, slot in self.slots.items():
            value = values.get(slot_no) if values else None
            slot.update(conds.get(slot_no, False), t, value, self._sink)

    def ack_all(self, t: float) -> bool:
        acked = [s.ack(t, None, self._sink) for s in self.slots.values()]  # квитировать все, не до первого
        return any(acked)

    def ack_mask(self, mask: int, t: float) -> None:
        for slot_no, slot in self.slots.items():
            if mask & (1 << slot_no):
                slot.ack(t, None, self._sink)

    def shelve_mask(self, mask: int, t: float) -> None:
        for slot_no, slot in self.slots.items():
            if mask & (1 << slot_no):
                slot.shelve(t, None, self._sink)

    def unshelve_mask(self, mask: int, t: float) -> None:
        for slot_no, slot in self.slots.items():
            if mask & (1 << slot_no):
                slot.unshelve(t, None, self._sink)

    def set_oos(self, oos: bool, t: float) -> None:
        for slot in self.slots.values():
            slot.set_oos(oos, t, self._sink)

    @property
    def w_active(self) -> int:
        return sum(1 << n for n, s in self.slots.items() if s.active)

    @property
    def w_unack(self) -> int:
        return sum(1 << n for n, s in self.slots.items() if s.unack)

    @property
    def w_shelved(self) -> int:
        return sum(1 << n for n, s in self.slots.items() if s.oos or s.shelved_until is not None)

    @property
    def prio_unack(self) -> AlarmPriority:
        prios = [s.priority for s in self.slots.values() if s.unack]
        return max(prios, default=AlarmPriority.NONE)

    def any_active(self, min_priority: AlarmPriority = AlarmPriority.LOW) -> bool:
        return any(s.active and s.priority >= min_priority for s in self.slots.values())
