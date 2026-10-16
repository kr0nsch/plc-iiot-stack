"""Почасовая агрегация: уровень, откачанный объём, моточасы и пуски насосов, тревоги.

Модель данных — «удержание последнего значения» (zero-order hold): значение действует от своей
отметки времени до следующей, но не дольше max_gap. Так одинаково обрабатываются периодический
опрос OPC UA и публикация MQTT «по изменению плюс периодически». Где данных нет, час получает
пустые ячейки, а колонка полноты данных показывает долю часа, покрытую уровнем и расходом.

Методика (подробно — report/README.md):
- уровень: минимум, максимум и средневзвешенное по времени значение LT101;
- объём: интеграл расхода FT202 (м³/ч × ч);
- моточасы и пуски: приращения счётчиков ПЛК RunTime (ч) и Starts; уменьшение счётчика —
  сброс (приращение = новое значение). Без счётчиков — по признаку Running (время в работе и
  фронты FALSE → TRUE);
- тревоги: события срабатывания из InfluxDB (reason = Activated) или фронты битов слов
  `<DEV>.AlmActive` при опросе OPC UA (бит = слот тревоги, scada_alarms.csv).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from kns_report.config import StationConfig
from kns_report.samples import Point, SeriesSet, Value
from kns_report.tagmodel import AlarmDef, TagInfo, alarm_devices, device_title
from kns_report.timeutil import HOUR, hour_starts

PRIORITY_BUCKETS = ("High", "Medium", "Low")
# Critical (резерв библиотеки под аварийный уровень) считается вместе с High
_BUCKET_OF = {"Critical": "High", "High": "High", "Medium": "Medium", "Low": "Low"}
# Уменьшение счётчика наработки меньше допуска — погрешность REAL, а не сброс
_RUNTIME_RESET_TOLERANCE_H = 1e-3
_WORD_BITS = 16


@dataclass
class PumpHour:
    run_h: float | None
    starts: int | None


@dataclass
class HourRow:
    start: datetime
    end: datetime
    level_min_m: float | None
    level_avg_m: float | None
    level_max_m: float | None
    volume_m3: float | None
    pumps: dict[str, PumpHour]
    alarms_total: int
    alarms_by_priority: dict[str, int]
    coverage: float


@dataclass(frozen=True)
class AlarmEvent:
    ts: datetime
    code: str
    device: str
    slot: int
    priority: str
    text: str


@dataclass
class PumpDay:
    device: str
    title: str
    run_method: str
    starts_method: str
    run_h: float | None
    starts: int | None
    run_total_h: float | None
    starts_total: int | None


@dataclass
class DailyReport:
    station_name: str
    station_code: str
    period_start: datetime
    period_end: datetime
    source: str
    generated_at: datetime
    hours: list[HourRow]
    events: list[AlarmEvent]
    pumps: list[PumpDay]
    level_min_m: float | None
    level_avg_m: float | None
    level_max_m: float | None
    volume_m3: float | None
    alarms_total: int
    alarms_by_priority: dict[str, int]
    coverage: float
    level_limits: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Acc:
    dur_s: float = 0.0
    wsum: float = 0.0
    vmin: float | None = None
    vmax: float | None = None

    def add(self, value: float, dur_s: float) -> None:
        self.dur_s += dur_s
        self.wsum += value * dur_s
        self.vmin = value if self.vmin is None else min(self.vmin, value)
        self.vmax = value if self.vmax is None else max(self.vmax, value)

    @property
    def avg(self) -> float | None:
        return self.wsum / self.dur_s if self.dur_s > 0 else None


def _finite(value: Value) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def hold_segments(
    points: list[Point], max_gap: timedelta, horizon: datetime | None = None
) -> list[tuple[datetime, datetime, float]]:
    """Отрезки удержания [t_i, min(t_{i+1}, t_i + max_gap, horizon)) со значением; NaN/Inf — разрыв.

    horizon — граница известных данных (конец выборки OPC UA, «сейчас»): дальше значение не тянется.
    """
    segments = []
    for index, (ts, raw) in enumerate(points):
        value = _finite(raw)
        if value is None:
            continue
        end = ts + max_gap
        if index + 1 < len(points):
            end = min(end, points[index + 1][0])
        if horizon is not None:
            end = min(end, horizon)
        if end > ts:
            segments.append((ts, end, value))
    return segments


def _hour_index(ts: datetime, start: datetime) -> int:
    return (ts - start) // HOUR


def distribute(segments: list[tuple[datetime, datetime, float]], start: datetime, n_hours: int) -> list[_Acc]:
    """Разнести отрезки по часам периода [start, start + n_hours ч)."""
    accs = [_Acc() for _ in range(n_hours)]
    end = start + n_hours * HOUR
    for seg_start, seg_end, value in segments:
        a = max(seg_start, start)
        b = min(seg_end, end)
        while a < b:
            index = _hour_index(a, start)
            boundary = start + (index + 1) * HOUR
            stop = min(b, boundary)
            accs[index].add(value, (stop - a).total_seconds())
            a = stop
    return accs


def rising_edges(points: list[Point]) -> list[datetime]:
    """Моменты переходов FALSE → TRUE (первая точка ряда фронтом не считается)."""
    edges = []
    previous: bool | None = None
    for ts, raw in points:
        value = _finite(raw)
        if value is None:
            continue
        state = value != 0.0
        if previous is False and state:
            edges.append(ts)
        previous = state
    return edges


def counter_increments(points: list[Point], tolerance: float = 0.0) -> list[tuple[datetime, datetime, float]]:
    """Приращения счётчика между соседними точками; уменьшение больше допуска — сброс."""
    result = []
    previous: tuple[datetime, float] | None = None
    for ts, raw in points:
        value = _finite(raw)
        if value is None:
            continue
        if previous is not None:
            delta = value - previous[1]
            if delta < 0:
                delta = 0.0 if -delta <= tolerance else value
            if delta > 0:
                result.append((previous[0], ts, delta))
        previous = (ts, value)
    return result


def _spread(
    increments: list[tuple[datetime, datetime, float]], start: datetime, n_hours: int, linear: bool
) -> list[float]:
    """Сумма приращений по часам: linear — пропорционально времени, иначе — в момент t_cur."""
    totals = [0.0] * n_hours
    end = start + n_hours * HOUR
    for t_prev, t_cur, delta in increments:
        if not linear or t_cur <= t_prev:
            if start <= t_cur < end:
                totals[_hour_index(t_cur, start)] += delta
            continue
        span = (t_cur - t_prev).total_seconds()
        a, b = max(t_prev, start), min(t_cur, end)
        while a < b:
            index = _hour_index(a, start)
            stop = min(b, start + (index + 1) * HOUR)
            totals[index] += delta * (stop - a).total_seconds() / span
            a = stop
    return totals


def _known_hours(points: list[Point], start: datetime, n_hours: int) -> list[bool]:
    """Час «известен» счётчику, если пересекается с интервалом [первая точка, последняя точка]."""
    if len(points) < 2:
        return [False] * n_hours
    first, last = points[0][0], points[-1][0]
    result = []
    for index in range(n_hours):
        h_start = start + index * HOUR
        h_end = h_start + HOUR
        result.append(h_start < last and h_end > first)
    return result


def _last_value_before(points: list[Point], ts: datetime) -> float | None:
    value = None
    for p_ts, raw in points:
        if p_ts >= ts:
            break
        finite = _finite(raw)
        if finite is not None:
            value = finite
    return value


def _points_in(points: list[Point], start: datetime, end: datetime) -> int:
    return sum(1 for ts, _ in points if start <= ts < end)


def _alarm_events(
    series: SeriesSet,
    devices: list[str],
    defs: dict[tuple[str, int], AlarmDef],
    start: datetime,
    end: datetime,
) -> list[AlarmEvent]:
    events = []
    for device in devices:
        previous: int | None = None
        for ts, raw in series.get(f"{device}.AlmActive"):
            number = _finite(raw)
            if number is None:
                continue
            word = int(number) & 0xFFFF
            if previous is not None and start <= ts < end:
                rising = word & ~previous
                for slot in range(_WORD_BITS):
                    if rising >> slot & 1:
                        known = defs.get((device, slot))
                        events.append(
                            AlarmEvent(
                                ts=ts,
                                code=known.code if known else f"{device}.BIT{slot}",
                                device=device,
                                slot=slot,
                                priority=known.priority if known else "Unknown",
                                text=known.text if known else "",
                            )
                        )
            previous = word
    events.sort(key=lambda e: (e.ts, e.code))
    return events


def _events_from_codes(
    activations: list[tuple[datetime, str]],
    devices: set[str],
    defs: dict[str, AlarmDef],
    start: datetime,
    end: datetime,
) -> list[AlarmEvent]:
    events = []
    for ts, code in activations:
        if not start <= ts < end:
            continue
        known = defs.get(code)
        device = known.device if known else code.partition(".")[0]
        if device not in devices:
            continue
        events.append(
            AlarmEvent(
                ts=ts,
                code=code,
                device=device,
                slot=known.slot if known else -1,
                priority=known.priority if known else "Unknown",
                text=known.text if known else "",
            )
        )
    events.sort(key=lambda e: (e.ts, e.code))
    return events


def build_report(
    series: SeriesSet,
    station: StationConfig,
    tags: dict[str, TagInfo],
    alarms: list[AlarmDef],
    start: datetime,
    end: datetime,
    source: str,
    generated_at: datetime,
    data_end: datetime | None = None,
    activations: list[tuple[datetime, str]] | None = None,
) -> DailyReport:
    """Почасовой отчёт за [start, end) (границы — начала местных часов).

    data_end — граница известных данных: последнее значение не удерживается дальше неё.
    activations — срабатывания тревог [(время, код)] из событий InfluxDB; без них тревоги
    считаются по фронтам слов `<DEV>.AlmActive` в series.
    """
    hours = hour_starts(start, end)
    n = len(hours)
    warnings: list[str] = []

    def series_or_warn(tag: str) -> list[Point]:
        points = series.get(tag)
        if not points:
            warnings.append(f"нет данных по тегу {tag}")
        return points

    level = distribute(hold_segments(series_or_warn(station.level_tag), station.analog_max_gap, data_end), start, n)
    flow = distribute(hold_segments(series_or_warn(station.flow_tag), station.analog_max_gap, data_end), start, n)

    pump_hours: dict[str, list[PumpHour]] = {}
    pump_days: list[PumpDay] = []
    lookback_start = start - station.discrete_max_gap
    for pump in station.pumps:
        running = series.get(f"{pump}.Running")
        starts_ctr = series.get(f"{pump}.Starts")
        runtime_ctr = series.get(f"{pump}.RunTime")
        want_counters = station.pump_method in ("auto", "counters")
        want_state = station.pump_method in ("auto", "state")
        use_rt = want_counters and _points_in(runtime_ctr, lookback_start, end) >= 2
        use_st = want_counters and _points_in(starts_ctr, lookback_start, end) >= 2
        has_running = want_state and bool(running)

        run_acc = (
            distribute(hold_segments(running, station.discrete_max_gap, data_end), start, n) if has_running else []
        )
        if use_rt:
            run_vals = _spread(counter_increments(runtime_ctr, _RUNTIME_RESET_TOLERANCE_H), start, n, True)
            known = _known_hours(runtime_ctr, start, n)
            run_h: list[float | None] = [v if k else None for v, k in zip(run_vals, known, strict=True)]
            run_method = "counters"
        elif has_running:
            run_h = [acc.wsum / 3600.0 if acc.dur_s > 0 else None for acc in run_acc]
            run_method = "state"
        else:
            run_h = [None] * n
            run_method = "none"

        if use_st:
            st_vals = _spread(counter_increments(starts_ctr), start, n, False)
            known = _known_hours(starts_ctr, start, n)
            starts: list[int | None] = [round(v) if k else None for v, k in zip(st_vals, known, strict=True)]
            starts_method = "counters"
        elif has_running:
            counts = [0] * n
            for edge in rising_edges(running):
                if start <= edge < end:
                    counts[_hour_index(edge, start)] += 1
            starts = [c if (acc.dur_s > 0 or c) else None for c, acc in zip(counts, run_acc, strict=True)]
            starts_method = "state"
        else:
            starts = [None] * n
            starts_method = "none"

        if run_method == "none" and starts_method == "none":
            warnings.append(f"нет данных по насосу {pump} (Running, Starts, RunTime)")
        pump_hours[pump] = [PumpHour(r, s) for r, s in zip(run_h, starts, strict=True)]
        run_known = [v for v in run_h if v is not None]
        starts_known = [v for v in starts if v is not None]
        rt_total = _last_value_before(runtime_ctr, end)
        st_total = _last_value_before(starts_ctr, end)
        pump_days.append(
            PumpDay(
                device=pump,
                title=device_title(tags, pump),
                run_method=run_method,
                starts_method=starts_method,
                run_h=sum(run_known) if run_known else None,
                starts=sum(starts_known) if starts_known else None,
                run_total_h=rt_total,
                starts_total=round(st_total) if st_total is not None else None,
            )
        )

    devices = list(station.alarm_devices) or alarm_devices(alarms)
    if activations is None:
        defs = {(a.device, a.slot): a for a in alarms}
        events = _alarm_events(series, devices, defs, start, end)
    else:
        events = _events_from_codes(activations, set(devices), {a.code: a for a in alarms}, start, end)

    rows = []
    for index, h_start in enumerate(hours):
        h_events = [e for e in events if h_start <= e.ts < h_start + HOUR]
        by_prio = dict.fromkeys(PRIORITY_BUCKETS, 0)
        for event in h_events:
            bucket = _BUCKET_OF.get(event.priority)
            if bucket:
                by_prio[bucket] += 1
        lv, fl = level[index], flow[index]
        rows.append(
            HourRow(
                start=h_start,
                end=h_start + HOUR,
                level_min_m=lv.vmin,
                level_avg_m=lv.avg,
                level_max_m=lv.vmax,
                volume_m3=fl.wsum / 3600.0 if fl.dur_s > 0 else None,
                pumps={pump: pump_hours[pump][index] for pump in station.pumps},
                alarms_total=len(h_events),
                alarms_by_priority=by_prio,
                coverage=min(lv.dur_s, fl.dur_s) / HOUR.total_seconds(),
            )
        )

    level_dur = sum(a.dur_s for a in level)
    level_mins = [a.vmin for a in level if a.vmin is not None]
    level_maxs = [a.vmax for a in level if a.vmax is not None]
    volumes = [r.volume_m3 for r in rows if r.volume_m3 is not None]
    totals = dict.fromkeys(PRIORITY_BUCKETS, 0)
    for row in rows:
        for key, count in row.alarms_by_priority.items():
            totals[key] += count

    limits: dict[str, float] = {}
    level_info = tags.get(station.level_tag)
    if level_info is not None:
        for key in ("hh", "h", "l", "ll"):
            limit = getattr(level_info, f"alarm_{key}")
            if limit is not None:
                limits[key.upper()] = limit

    return DailyReport(
        station_name=station.name,
        station_code=station.area,
        period_start=start,
        period_end=end,
        source=source,
        generated_at=generated_at,
        hours=rows,
        events=events,
        pumps=pump_days,
        level_min_m=min(level_mins) if level_mins else None,
        level_avg_m=sum(a.wsum for a in level) / level_dur if level_dur > 0 else None,
        level_max_m=max(level_maxs) if level_maxs else None,
        volume_m3=sum(volumes) if volumes else None,
        alarms_total=len(events),
        alarms_by_priority=totals,
        coverage=sum(r.coverage for r in rows) / n if n else 0.0,
        level_limits=limits,
        warnings=warnings,
    )
