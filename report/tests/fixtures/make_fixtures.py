"""Генератор тестовых данных отчёта: синтетические сутки КНС-1 в формате ответа InfluxDB.

Запуск (из report/): python tests/fixtures/make_fixtures.py

Данные синтетические (не запись с реального объекта): упрощённая модель станции с шагом 10 с
публикует теги так, как их публикует ПЛК в MQTT (schema/: топики vodokanal/kns1/station/<device>/
<metric>, тревоги — события .../alarm/<SUFFIX>), — по изменению плюс периодически. Файлы повторяют
ответы InfluxDB 2 на запросы `kns_report.influx.build_flux` (influx_day.csv: measurement telemetry,
метрики level, flow, running, starts, run_hours; Telegraf пишет числа JSON как double) и
`build_alarm_flux` (influx_day_alarms.csv: срабатывания, reason = Activated). Рядом — «эталон»
по плотной модели (каждые 10 с): тесты сравнивают с ним отчёт, построенный по разреженным данным.
Выборка «как с OPC UA» (opcua_window.jsonl) содержит и слова тревог <DEV>.AlmActive.

Сценарий суток 15.10.2026 (МСК, UTC+3):
- суточный профиль притока с утренним и вечерним пиком, «ливень» 14:10–15:20;
- ступенчатое управление: ведущий насос — пуск 2,6 м, второй — 3,2 м, все исправные — 4,0 м,
  останов вторых — 2,2 м, всех — 1,0 м; чередование — по кругу при каждом пуске;
- первая попытка пуска Н2 после 09:00 — отказ пуска (P102.FTS), АВР, сброс через 35 мин;
- 10:05–10:25 открыта дверь павильона (ZS404.ALM);
- уровень выше H 3,5 м и HH 4,0 м во время ливня (LT101.H, LT101.HH);
- 03:20–03:45 разрыв передачи данных (перезапуск сборщика): точек нет.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
MSK = timezone(timedelta(hours=3))
DAY_START = datetime(2026, 10, 15, 0, 0, tzinfo=MSK)
# Запрос отчёта начинается раньше суток на lookback = max(analog_max_gap, discrete_max_gap) = 2 ч
SIM_START = DAY_START - timedelta(hours=2)
SIM_END = DAY_START + timedelta(days=1)
DT_S = 10
GAP = (datetime(2026, 10, 15, 3, 20, tzinfo=MSK), datetime(2026, 10, 15, 3, 45, tzinfo=MSK))

AREA_M2 = 40.0
PUMP_FLOW_M3H = {1: 120.0, 2: 210.0, 3: 270.0}  # расход по числу работающих насосов
PUMPS = ("P101", "P102", "P103")
LEVEL_DEADBAND_M = 0.05
PERIOD_ANALOG = timedelta(minutes=5)
PERIOD_PUMP = timedelta(minutes=15)
PERIOD_ALARM = timedelta(hours=2)
LIMIT_H, LIMIT_HH, HYST = 3.5, 4.0, 0.05

# Слоты тревог (scada_alarms.csv): LT101 1 = H, 0 = HH; P102 0 = FTS; ZS404 0 = ALM
ALARM_DEVICES = (
    "P101",
    "P102",
    "P103",
    "V1",
    "LT101",
    "LS102",
    "LS103",
    "IT111",
    "TS112",
    "MS113",
    "IT121",
    "TS122",
    "MS123",
    "IT131",
    "TS132",
    "MS133",
    "PT201",
    "FT202",
    "LS203",
    "ES301",
    "YS302",
    "YS303",
    "AT401",
    "AT402",
    "TT403",
    "ZS404",
    "YS405",
)


def inflow_m3h(ts: datetime) -> float:
    h = ts.astimezone(MSK).hour + ts.astimezone(MSK).minute / 60.0 + ts.astimezone(MSK).second / 3600.0
    q = 55.0 + 30.0 * math.exp(-(((h - 8.0) / 2.0) ** 2)) + 35.0 * math.exp(-(((h - 20.0) / 2.5) ** 2))
    q -= 20.0 * math.exp(-(((h - 4.0) / 2.0) ** 2))
    storm = 14.0 + 10.0 / 60.0 <= h < 15.0 + 20.0 / 60.0
    if storm:
        q += 250.0 * math.sin(math.pi * (h - 14.0 - 10.0 / 60.0) / (70.0 / 60.0))
    return q


@dataclass
class Pump:
    tag: str
    running: bool = False
    run_s: float = 0.0
    starts: int = 0
    faulted: bool = False


@dataclass
class Sim:
    level: float = 1.8
    pumps: dict[str, Pump] = field(default_factory=dict)
    words: dict[str, int] = field(default_factory=dict)
    last_started: int = -1


def _bit(word: int, slot: int, on: bool) -> int:
    return word | (1 << slot) if on else word & ~(1 << slot)


def simulate() -> list[tuple[datetime, Sim, float]]:
    """Плотная модель: [(время, состояние, расход)] каждые DT_S секунд."""
    sim = Sim(
        pumps={
            "P101": Pump("P101", run_s=1523.4 * 3600, starts=812),
            "P102": Pump("P102", run_s=1519.8 * 3600, starts=809),
            "P103": Pump("P103", run_s=1526.1 * 3600, starts=815),
        },
        words=dict.fromkeys(ALARM_DEVICES, 0),
    )
    states: list[tuple[datetime, Sim, float]] = []
    fts_armed = datetime(2026, 10, 15, 9, 0, tzinfo=MSK)
    fts_done = False
    reset_at: datetime | None = None
    door = (datetime(2026, 10, 15, 10, 5, tzinfo=MSK), datetime(2026, 10, 15, 10, 25, tzinfo=MSK))
    ts = SIM_START
    while ts < SIM_END:
        running = [p for p in sim.pumps.values() if p.running]

        def start_one(now: datetime) -> bool:
            nonlocal fts_done, reset_at
            for shift in range(1, len(PUMPS) + 1):
                index = (sim.last_started + shift) % len(PUMPS)
                pump = sim.pumps[PUMPS[index]]
                if pump.running or pump.faulted:
                    continue
                sim.last_started = index
                if pump.tag == "P102" and now >= fts_armed and not fts_done:
                    # отказ пуска: ОС нет, насос в отказе, тревога FTS, АВР — следующий по кругу
                    fts_done = True
                    pump.faulted = True
                    reset_at = now + timedelta(minutes=35)
                    sim.words["P102"] = _bit(sim.words["P102"], 0, True)
                    return start_one(now)
                pump.running = True
                pump.starts += 1
                return True
            return False

        if (not running and sim.level >= 2.6) or (len(running) == 1 and sim.level >= 3.2):
            start_one(ts)
        elif sim.level >= LIMIT_HH:
            while start_one(ts):
                pass
        if sim.level <= 1.0:
            for pump in running:
                pump.running = False
        elif sim.level <= 2.2 and len(running) > 1:
            for pump in sorted(running, key=lambda p: -p.run_s)[: len(running) - 1]:
                pump.running = False
        if reset_at is not None and ts >= reset_at and sim.pumps["P102"].faulted:
            sim.pumps["P102"].faulted = False
            sim.words["P102"] = _bit(sim.words["P102"], 0, False)

        lt = sim.words["LT101"]
        lt = _bit(lt, 1, sim.level >= LIMIT_H or (bool(lt & 2) and sim.level > LIMIT_H - HYST))
        lt = _bit(lt, 0, sim.level >= LIMIT_HH or (bool(lt & 1) and sim.level > LIMIT_HH - HYST))
        sim.words["LT101"] = lt
        sim.words["ZS404"] = _bit(sim.words["ZS404"], 0, door[0] <= ts < door[1])

        n_run = sum(1 for p in sim.pumps.values() if p.running)
        flow = PUMP_FLOW_M3H.get(n_run, 0.0)
        snapshot = Sim(
            level=sim.level,
            pumps={k: Pump(p.tag, p.running, p.run_s, p.starts, p.faulted) for k, p in sim.pumps.items()},
            words=dict(sim.words),
        )
        states.append((ts, snapshot, flow))
        sim.level = max(0.0, sim.level + (inflow_m3h(ts) - flow) * DT_S / 3600.0 / AREA_M2)
        for pump in sim.pumps.values():
            if pump.running:
                pump.run_s += DT_S
        ts += timedelta(seconds=DT_S)
    return states


def publish(states: list[tuple[datetime, Sim, float]]) -> dict[str, list[tuple[datetime, float | int | bool]]]:
    """Публикация «по изменению + периодически» с разрывом GAP."""
    out: dict[str, list[tuple[datetime, float | int | bool]]] = {}
    last: dict[str, tuple[datetime, float | int | bool]] = {}

    def emit(tag: str, ts: datetime, value: float | int | bool, period: timedelta, changed: bool) -> None:
        if GAP[0] <= ts < GAP[1]:
            return
        prev = last.get(tag)
        periodic = prev is None or (ts - SIM_START) % period == timedelta(0)
        if changed or periodic:
            out.setdefault(tag, []).append((ts, value))
            last[tag] = (ts, value)

    for ts, sim, flow in states:
        prev_level = last.get("LT101.Value")
        level = round(sim.level, 3)
        emit(
            "LT101.Value",
            ts,
            level,
            PERIOD_ANALOG,
            prev_level is not None and abs(level - float(prev_level[1])) >= LEVEL_DEADBAND_M,
        )
        prev_flow = last.get("FT202.Value")
        emit("FT202.Value", ts, flow, PERIOD_ANALOG, prev_flow is not None and prev_flow[1] != flow)
        for pump in sim.pumps.values():
            prev_run = last.get(f"{pump.tag}.Running")
            changed = prev_run is not None and prev_run[1] != pump.running
            emit(f"{pump.tag}.Running", ts, pump.running, PERIOD_PUMP, changed)
            prev_st = last.get(f"{pump.tag}.Starts")
            emit(f"{pump.tag}.Starts", ts, pump.starts, PERIOD_PUMP, prev_st is not None and prev_st[1] != pump.starts)
            emit(f"{pump.tag}.RunTime", ts, round(pump.run_s / 3600.0, 6), PERIOD_PUMP, changed)
        for device, word in sim.words.items():
            prev_w = last.get(f"{device}.AlmActive")
            emit(f"{device}.AlmActive", ts, word, PERIOD_ALARM, prev_w is not None and prev_w[1] != word)
    return out


# Метрики телеметрии по schema/telemetry_catalog.csv
METRIC = {
    "LT101.Value": "level",
    "FT202.Value": "flow",
    "Running": "running",
    "Starts": "starts",
    "RunTime": "run_hours",
}
# Суффиксы тревог модели (scada_alarms.csv): (устройство, слот) → суффикс
SUFFIX = {("LT101", 0): "HH", ("LT101", 1): "H", ("P102", 0): "FTS", ("ZS404", 0): "ALM"}


def _metric(tag: str) -> tuple[str, str]:
    device, prop = tag.split(".", 1)
    return device, METRIC.get(tag, METRIC.get(prop, prop))


def _fmt_time(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt_value(value: float | int | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)
    return str(value)


def annotated_csv(series: dict[str, list[tuple[datetime, float | int | bool]]]) -> str:
    """Ответ InfluxDB на запрос телеметрии: таблица на ряд (device, metric), _value — double."""
    lines = [
        "#datatype,string,long,dateTime:RFC3339,double,string,string",
        "#group,false,false,false,false,true,true",
        "#default,_result,,,,,",
        ",result,table,_time,_value,device,metric",
    ]
    tables = sorted((_metric(tag), tag) for tag in series if not tag.endswith(".AlmActive"))
    for table, ((device, metric), tag) in enumerate(tables):
        for ts, value in series[tag]:
            lines.append(f",,{table},{_fmt_time(ts)},{_fmt_value(float(value))},{device},{metric}")
    return "\n".join(lines) + "\n\n"


def alarm_events(states: list[tuple[datetime, Sim, float]]) -> list[tuple[datetime, str, str]]:
    """События срабатывания (фронт бита слова тревог) вне разрыва передачи: (время, устройство, суффикс)."""
    events = []
    prev = states[0][1].words
    for ts, sim, _ in states[1:]:
        for device, word in sim.words.items():
            rising = word & ~prev[device]
            for slot in range(16):
                if rising >> slot & 1 and not GAP[0] <= ts < GAP[1]:
                    events.append((ts, device, SUFFIX[(device, slot)]))
        prev = sim.words
    return events


def alarm_csv(events: list[tuple[datetime, str, str]]) -> str:
    """Ответ InfluxDB на запрос тревог: таблица на (device, suffix), _value — строка reason."""
    lines = [
        "#datatype,string,long,dateTime:RFC3339,string,string,string",
        "#group,false,false,false,false,true,true",
        "#default,_result,,,,,",
        ",result,table,_time,_value,device,suffix",
    ]
    groups = sorted({(device, suffix) for _, device, suffix in events})
    for table, (device, suffix) in enumerate(groups):
        for ts, d, sfx in events:
            if (d, sfx) == (device, suffix):
                lines.append(f",,{table},{_fmt_time(ts)},Activated,{device},{suffix}")
    return "\n".join(lines) + "\n\n"


def truth(states: list[tuple[datetime, Sim, float]]) -> dict[str, object]:
    """Эталон по плотной модели для суток DAY_START (час — местный)."""
    hours: list[dict[str, object]] = []
    for h in range(24):
        a = DAY_START + timedelta(hours=h)
        b = a + timedelta(hours=1)
        window = [(ts, s, f) for ts, s, f in states if a <= ts < b]
        prev = [(ts, s, f) for ts, s, f in states if ts < a][-1]
        run_h = {p: sum(DT_S for _, s, _ in window if s.pumps[p].running) / 3600.0 for p in PUMPS}
        last_state = window[-1][1]
        starts = {p: last_state.pumps[p].starts - prev[1].pumps[p].starts for p in PUMPS}
        alarms: list[str] = []
        prev_words = prev[1].words
        for ts, s, _ in window:
            for device, word in s.words.items():
                rising = word & ~prev_words[device]
                alarms += [f"{device}:{slot}@{ts.astimezone(MSK):%H:%M:%S}" for slot in range(16) if rising >> slot & 1]
            prev_words = s.words
        levels = [s.level for _, s, _ in window]
        hours.append(
            {
                "hour": h,
                "volume_m3": sum(f for _, _, f in window) * DT_S / 3600.0,
                "level_min_m": min(levels),
                "level_max_m": max(levels),
                "run_h": run_h,
                "starts": starts,
                "alarms": alarms,
            }
        )
    end_state = states[-1][1]
    return {
        "day": DAY_START.date().isoformat(),
        "gap": [_fmt_time(GAP[0]), _fmt_time(GAP[1])],
        "hours": hours,
        "run_total_h": {p: end_state.pumps[p].run_s / 3600.0 for p in PUMPS},
        "starts_total": {p: end_state.pumps[p].starts for p in PUMPS},
    }


def opcua_window(states: list[tuple[datetime, Sim, float]]) -> str:
    """Выборка «как с OPC UA» 14:13–14:21 (отказ пуска Н2 и АВР) с шагом 10 с (широкий JSON Lines)."""
    a = datetime(2026, 10, 15, 14, 13, tzinfo=MSK)
    b = datetime(2026, 10, 15, 14, 21, tzinfo=MSK)
    lines = []
    for ts, sim, flow in states:
        if not a <= ts <= b:
            continue
        values: dict[str, float | int | bool] = {"LT101.Value": round(sim.level, 3), "FT202.Value": flow}
        for pump in sim.pumps.values():
            values[f"{pump.tag}.Running"] = pump.running
            values[f"{pump.tag}.Starts"] = pump.starts
            values[f"{pump.tag}.RunTime"] = round(pump.run_s / 3600.0, 6)
        for device, word in sim.words.items():
            values[f"{device}.AlmActive"] = word
        lines.append(json.dumps({"ts": _fmt_time(ts), "values": values}, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def main() -> None:
    states = simulate()
    series = publish(states)
    (HERE / "influx_day.csv").write_text(annotated_csv(series), encoding="utf-8", newline="\n")
    (HERE / "influx_day_alarms.csv").write_text(alarm_csv(alarm_events(states)), encoding="utf-8", newline="\n")
    (HERE / "influx_day_truth.json").write_text(
        json.dumps(truth(states), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    (HERE / "opcua_window.jsonl").write_text(opcua_window(states), encoding="utf-8", newline="\n")
    print(f"точек: {sum(len(v) for v in series.values())}, рядов: {len(series)}")


if __name__ == "__main__":
    main()
