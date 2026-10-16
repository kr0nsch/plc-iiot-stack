"""Почасовая агрегация на коротких рядах с результатом, посчитанным вручную."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from kns_report.aggregate import (
    DailyReport,
    build_report,
    counter_increments,
    distribute,
    hold_segments,
    rising_edges,
)
from kns_report.config import ReportConfig
from kns_report.samples import SeriesSet, Value
from kns_report.tagmodel import AlarmDef, TagInfo

from .conftest import GENERATED_AT, MSK

T0 = datetime(2026, 10, 15, 10, 0, tzinfo=MSK)
T2 = T0 + timedelta(hours=2)


def at(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


def make_series(data: dict[str, list[tuple[float, Value]]]) -> SeriesSet:
    series = SeriesSet()
    for tag, points in data.items():
        for minute, value in points:
            series.add(tag, at(minute), value)
    return series.sort()


def report_for(
    data: dict[str, list[tuple[float, Value]]],
    cfg: ReportConfig,
    tags: dict[str, TagInfo],
    alarms: list[AlarmDef],
    **station: object,
) -> DailyReport:
    st = replace(cfg.station, **station)  # type: ignore[arg-type]
    return build_report(make_series(data), st, tags, alarms, T0, T2, "тест", GENERATED_AT)


FLOW_FULL: list[tuple[float, Value]] = [(0, 0.0), (60, 0.0)]


def test_hold_segments_respects_gap_and_nan() -> None:
    points: list[tuple[datetime, Value]] = [(at(0), 1.0), (at(5), float("nan")), (at(30), 2.0), (at(31), 3.0)]
    segments = hold_segments(points, timedelta(minutes=10))
    assert segments == [(at(0), at(5), 1.0), (at(30), at(31), 2.0), (at(31), at(41), 3.0)]


def test_distribute_splits_at_hour_boundary() -> None:
    accs = distribute([(at(50), at(70), 2.0)], T0, 2)
    assert accs[0].dur_s == 600 and accs[1].dur_s == 600
    assert accs[0].wsum == 1200.0
    assert accs[1].vmin == accs[1].vmax == 2.0


def test_level_min_avg_max_time_weighted(cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]) -> None:
    data: dict[str, list[tuple[float, Value]]] = {
        "LT101.Value": [(0, 2.0), (15, 3.0), (45, 1.0), (90, 4.0)],
        "FT202.Value": FLOW_FULL,
    }
    report = report_for(data, cfg, tags, alarms, analog_max_gap=timedelta(hours=1))
    h10, h11 = report.hours
    assert (h10.level_min_m, h10.level_max_m) == (1.0, 3.0)
    assert h10.level_avg_m == pytest.approx(2.25)
    assert (h11.level_min_m, h11.level_max_m) == (1.0, 4.0)
    assert h11.level_avg_m == pytest.approx(2.5)
    assert report.level_avg_m == pytest.approx(2.375)
    assert (report.level_min_m, report.level_max_m) == (1.0, 4.0)


def test_volume_is_flow_integral(cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]) -> None:
    data: dict[str, list[tuple[float, Value]]] = {
        "LT101.Value": [(0, 2.0), (60, 2.0)],
        "FT202.Value": [(0, 120.0), (30, 0.0), (50, 60.0)],
    }
    report = report_for(data, cfg, tags, alarms, analog_max_gap=timedelta(hours=1))
    h10, h11 = report.hours
    assert h10.volume_m3 == pytest.approx(70.0)
    assert h11.volume_m3 == pytest.approx(50.0)  # удержание 60 м³/ч до 11:50
    assert h11.coverage == pytest.approx(50 / 60)
    assert report.volume_m3 == pytest.approx(120.0)


def test_gap_longer_than_max_gap_lowers_coverage(
    cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]
) -> None:
    data: dict[str, list[tuple[float, Value]]] = {
        "LT101.Value": [(0, 2.0), (40, 2.5)],
        "FT202.Value": [(m, 10.0) for m in range(0, 120, 5)],
    }
    report = report_for(data, cfg, tags, alarms, analog_max_gap=timedelta(minutes=10))
    h10, h11 = report.hours
    assert h10.coverage == pytest.approx(20 / 60)
    assert h10.level_avg_m == pytest.approx(2.25)
    assert h11.level_min_m is None and h11.level_avg_m is None and h11.coverage == 0.0
    assert h11.volume_m3 == pytest.approx(10.0)


def test_counter_increments_and_reset() -> None:
    points: list[tuple[datetime, Value]] = [(at(0), 50), (at(20), 51), (at(70), 53), (at(100), 2)]
    assert [inc for _, _, inc in counter_increments(points)] == [1, 2, 2]
    jitter: list[tuple[datetime, Value]] = [(at(0), 10.0), (at(1), 9.9995), (at(2), 10.5)]
    assert [round(inc, 4) for _, _, inc in counter_increments(jitter, 1e-3)] == [0.5005]


def test_pump_counters_hourly(cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]) -> None:
    data: dict[str, list[tuple[float, Value]]] = {
        "P101.RunTime": [(0, 100.0), (30, 100.25), (90, 100.75)],
        "P101.Starts": [(0, 50), (20, 51), (70, 53), (100, 2)],
        "P101.Running": [(0, True)],
    }
    report = report_for(data, cfg, tags, alarms, pumps=("P101",))
    h10, h11 = (row.pumps["P101"] for row in report.hours)
    assert h10.run_h == pytest.approx(0.5)  # 0,25 + половина приращения 10:30–11:30
    assert h11.run_h == pytest.approx(0.25)
    assert (h10.starts, h11.starts) == (1, 4)  # сброс счётчика в 11:40: +2
    day = report.pumps[0]
    assert (day.run_method, day.starts_method) == ("counters", "counters")
    assert day.run_h == pytest.approx(0.75)
    assert (day.starts, day.starts_total) == (5, 2)
    assert day.run_total_h == pytest.approx(100.75)
    assert day.title == "Насос Н1"


def test_pump_state_fallback(cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]) -> None:
    data: dict[str, list[tuple[float, Value]]] = {
        "P102.Running": [(0, False), (10, True), (40, False), (50, True), (80, False), (110, False)],
    }
    report = report_for(data, cfg, tags, alarms, pumps=("P102",))
    h10, h11 = (row.pumps["P102"] for row in report.hours)
    assert h10.run_h == pytest.approx(40 / 60)
    assert h11.run_h == pytest.approx(20 / 60)
    assert (h10.starts, h11.starts) == (2, 0)
    assert report.pumps[0].run_method == "state"
    assert report.pumps[0].run_total_h is None


def test_pump_method_state_ignores_counters(
    cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]
) -> None:
    data: dict[str, list[tuple[float, Value]]] = {
        "P101.RunTime": [(0, 100.0), (60, 109.0)],
        "P101.Running": [(0, False), (30, True)],
    }
    report = report_for(data, cfg, tags, alarms, pumps=("P101",), pump_method="state")
    assert report.hours[0].pumps["P101"].run_h == pytest.approx(0.5)
    assert report.pumps[0].starts == 1


def test_pump_without_data_is_empty_and_warned(
    cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]
) -> None:
    report = report_for({}, cfg, tags, alarms, pumps=("P103",))
    assert report.hours[0].pumps["P103"].run_h is None
    assert report.pumps[0].run_method == "none"
    assert any("P103" in w for w in report.warnings)
    assert any("LT101.Value" in w for w in report.warnings)


def test_rising_edges_skip_first_point() -> None:
    points: list[tuple[datetime, Value]] = [(at(0), True), (at(1), False), (at(2), 1.0), (at(3), True)]
    assert rising_edges(points) == [at(2)]


def test_alarm_edges_priorities_and_unknown_bits(
    cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]
) -> None:
    data: dict[str, list[tuple[float, Value]]] = {
        "P101.AlmActive": [(0, 0), (5, 0b1), (6, 0b1), (20, 0), (30, 0b10000001), (60, 0x8000)],
        "LT101.AlmActive": [(-60, 0), (-30, 0b1), (-20, 0), (75, 0b1)],
        "ZS404.AlmActive": [(0, 0b1), (10, 0b1)],  # активна до начала периода — не новое срабатывание
    }
    report = report_for(data, cfg, tags, alarms, alarm_devices=("P101", "LT101", "ZS404"))
    codes = [(e.ts, e.code, e.priority) for e in report.events]
    assert codes == [
        (at(5), "P101.FTS", "Medium"),
        (at(30), "P101.FTS", "Medium"),
        (at(30), "P101.SPD", "Low"),
        (at(60), "P101.BIT15", "Unknown"),
        (at(75), "LT101.HH", "High"),
    ]
    h10, h11 = report.hours
    assert h10.alarms_total == 3 and h10.alarms_by_priority == {"High": 0, "Medium": 2, "Low": 1}
    assert h11.alarms_total == 2 and h11.alarms_by_priority == {"High": 1, "Medium": 0, "Low": 0}
    assert report.alarms_total == 5
    assert report.alarms_by_priority == {"High": 1, "Medium": 2, "Low": 1}
    assert report.events[0].text == "Насос Н1: нет подтверждения пуска"


def test_all_alarm_devices_by_default(cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]) -> None:
    data: dict[str, list[tuple[float, Value]]] = {"YS405.AlmActive": [(0, 0), (1, 1)]}
    report = report_for(data, cfg, tags, alarms)
    assert [e.code for e in report.events] == ["YS405.ALM"]
    assert report.alarms_by_priority["High"] == 1


def test_level_limits_passed_to_report(cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]) -> None:
    report = report_for({}, cfg, tags, alarms)
    assert report.level_limits == {"HH": 4.0, "H": 3.5, "L": 0.8, "LL": 0.5}
    assert [r.start.isoformat() for r in report.hours] == ["2026-10-15T10:00:00+03:00", "2026-10-15T11:00:00+03:00"]
