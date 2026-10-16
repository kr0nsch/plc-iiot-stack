"""Инъекция отказов и автоматический сценарий демонстрации.

Отказы — те же, что в модели флагмана (02-flagship-pump-station.md: авария насоса, обрыв
датчика, потеря связи с ПЧ, залипание поплавка) плюс события павильона и электроснабжения.
Включаются узлами ``Simulation.Inject.<имя>`` OPC UA-сервера эмулятора или автоматическим
сценарием: он строит расписание из зерна (seed) для каждых модельных суток, поэтому прогон с
тем же зерном повторяется в точности.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

DAY_S = 86400.0

# имя → описание (для узлов OPC UA и документации)
FAULTS: dict[str, str] = {
    **{f"p{n}_vfd_trip": f"Насос Н{n}: авария ПЧ (реле аварии и слово состояния)" for n in (1, 2, 3)},
    **{f"p{n}_no_feedback": f"Насос Н{n}: нет ОС «в работе» (обрыв цепи реле ПЧ)" for n in (1, 2, 3)},
    **{f"p{n}_comm_loss": f"Насос Н{n}: потеря связи с ПЧ по Modbus RTU" for n in (1, 2, 3)},
    **{f"p{n}_clog": f"Насос Н{n}: засор рабочего колеса (рост тока, падение подачи)" for n in (1, 2, 3)},
    **{f"p{n}_overheat": f"Насос Н{n}: перегрев обмотки (TS1{n}2)" for n in (1, 2, 3)},
    **{f"p{n}_leak": f"Насос Н{n}: протечка в камеру статора (MS1{n}3)" for n in (1, 2, 3)},
    **{f"p{n}_local": f"Насос Н{n}: переключатель в «Местное», пуск по месту" for n in (1, 2, 3)},
    "lt101_wire_break": "LT101: обрыв линии 4–20 мА (0 мА)",
    "ls102_stuck": "LS102: залипание поплавка «аварийно высокий уровень» в сработавшем положении",
    "ls103_stuck": "LS103: залипание поплавка «сухой ход» в сработавшем положении",
    "power_loss": "ES301: пропадание напряжения на вводе",
    "ups_fault": "YS303: неисправность ИБП",
    "chamber_flood": "LS203: затопление камеры задвижек",
    "door_open": "ZS404: дверь павильона открыта",
    "fire": "YS405: сигнал пожарной сигнализации",
    "h2s_spike": "AT401: выброс сероводорода",
    "fan_fault": "V1: авария вентилятора (автомат защиты)",
}

# Разовые действия (не флаги)
ACTIONS: dict[str, str] = {"storm": "Начать «ливень» сейчас (пик 320 м³/ч, 2 ч)"}


@dataclass(frozen=True)
class ScenarioEvent:
    t: float  # модельное время, с
    kind: str  # inject | clear | command
    target: str  # имя отказа или тег команды
    value: bool | int | float = True


class AutoScenario:
    """Расписание отказов и действий «оператора» по модельным суткам."""

    def __init__(self, seed: int, t0_s: float = 0.0) -> None:
        self.seed = seed
        self.t0_s = t0_s
        self._cache: dict[int, list[ScenarioEvent]] = {}

    def events_of_day(self, day: int) -> list[ScenarioEvent]:
        cached = self._cache.get(day)
        if cached is not None:
            return cached
        if len(self._cache) > 64:
            self._cache.clear()
        rng = random.Random(f"kns-scenario:{self.seed}:{day}")
        base = day * DAY_S - self.t0_s
        ev: list[ScenarioEvent] = []

        def window(lo_h: float, hi_h: float, dur_lo_s: float, dur_hi_s: float) -> tuple[float, float]:
            start = base + rng.uniform(lo_h, hi_h) * 3600.0
            return start, start + rng.uniform(dur_lo_s, dur_hi_s)

        if rng.random() < 0.7:  # авария ПЧ: сброс оператором после устранения
            n = rng.randint(1, 3)
            a, b = window(0.0, 23.0, 600.0, 2400.0)
            ev += [
                ScenarioEvent(a, "inject", f"p{n}_vfd_trip"),
                ScenarioEvent(b, "clear", f"p{n}_vfd_trip"),
                ScenarioEvent(b + 120.0, "command", f"P10{n}.Cmd.Reset", True),
            ]
        if rng.random() < 0.8:  # плановый обход: дверь павильона
            a, b = window(8.0, 16.0, 1200.0, 3600.0)
            ev += [ScenarioEvent(a, "inject", "door_open"), ScenarioEvent(b, "clear", "door_open")]
        if rng.random() < 0.4:  # выброс сероводорода
            a, b = window(0.0, 23.0, 900.0, 1800.0)
            ev += [ScenarioEvent(a, "inject", "h2s_spike"), ScenarioEvent(b, "clear", "h2s_spike")]
        if rng.random() < 0.3:  # кратковременная потеря связи с ПЧ
            n = rng.randint(1, 3)
            a, b = window(0.0, 23.0, 60.0, 300.0)
            ev += [ScenarioEvent(a, "inject", f"p{n}_comm_loss"), ScenarioEvent(b, "clear", f"p{n}_comm_loss")]
        if rng.random() < 0.25:  # засор рабочего колеса: рост тока до прочистки
            n = rng.randint(1, 3)
            a, b = window(0.0, 20.0, 3600.0, 4 * 3600.0)
            ev += [ScenarioEvent(a, "inject", f"p{n}_clog"), ScenarioEvent(b, "clear", f"p{n}_clog")]
        if rng.random() < 0.15:  # пропадание питания
            a, b = window(0.0, 23.0, 120.0, 600.0)
            ev += [ScenarioEvent(a, "inject", "power_loss"), ScenarioEvent(b, "clear", "power_loss")]
        ev.sort(key=lambda e: e.t)
        self._cache[day] = ev
        return ev

    def due(self, t_prev: float, t_now: float) -> list[ScenarioEvent]:
        """События с t_prev < t ≤ t_now."""
        out: list[ScenarioEvent] = []
        d0 = math.floor((t_prev + self.t0_s) / DAY_S)
        d1 = math.floor((t_now + self.t0_s) / DAY_S)
        for day in range(d0, d1 + 1):
            out += [e for e in self.events_of_day(day) if t_prev < e.t <= t_now]
        return out
