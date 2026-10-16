"""Сутки по ответу InfluxDB (tests/fixtures/influx_day.csv) против эталона плотной модели.

Данные публикуются «по изменению + периодически», эталон посчитан по состоянию модели каждые
10 с (tests/fixtures/make_fixtures.py). Совпадать должны объём, моточасы, пуски и тревоги;
уровень — с точностью до зоны нечувствительности публикации (0,05 м).
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest

from kns_report.aggregate import DailyReport, build_report
from kns_report.cli import required_tags
from kns_report.config import ReportConfig
from kns_report.influx import parse_annotated_csv, rows_to_activations, rows_to_series
from kns_report.tagmodel import AlarmDef, TagInfo
from kns_report.timeutil import day_bounds

from .conftest import FIXTURES, GENERATED_AT, MSK

GAP_HOUR = 3
LEVEL_TOLERANCE_M = 0.06


@pytest.fixture(scope="module")
def truth() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / "influx_day_truth.json").read_text(encoding="utf-8"))
    return data


@pytest.fixture()
def day_report(cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]) -> DailyReport:
    rows = parse_annotated_csv((FIXTURES / "influx_day.csv").read_text(encoding="utf-8"))
    series = rows_to_series(cfg.influx, rows, required_tags(cfg.station, alarms, alarm_words=False))
    events = parse_annotated_csv((FIXTURES / "influx_day_alarms.csv").read_text(encoding="utf-8"))
    activations = rows_to_activations(cfg.influx, events)
    start, end = day_bounds(date(2026, 10, 15), MSK)
    return build_report(series, cfg.station, tags, alarms, start, end, "fixture", GENERATED_AT, end, activations)


def test_day_has_24_local_hours(day_report: DailyReport) -> None:
    assert len(day_report.hours) == 24
    assert day_report.hours[0].start.isoformat() == "2026-10-15T00:00:00+03:00"
    assert day_report.warnings == []


def test_volume_matches_dense_model(day_report: DailyReport, truth: dict[str, Any]) -> None:
    for row, ref in zip(day_report.hours, truth["hours"], strict=True):
        assert row.volume_m3 is not None
        if ref["hour"] == GAP_HOUR:
            assert row.volume_m3 <= ref["volume_m3"] + 1e-6
        else:
            assert row.volume_m3 == pytest.approx(ref["volume_m3"], abs=1e-6), ref["hour"]


def test_pump_hours_and_starts_match(day_report: DailyReport, truth: dict[str, Any]) -> None:
    for row, ref in zip(day_report.hours, truth["hours"], strict=True):
        for pump, expected in ref["run_h"].items():
            assert row.pumps[pump].run_h == pytest.approx(expected, abs=1e-6), (ref["hour"], pump)
            assert row.pumps[pump].starts == ref["starts"][pump], (ref["hour"], pump)
    for day in day_report.pumps:
        assert (day.run_method, day.starts_method) == ("counters", "counters")
        assert day.run_total_h == pytest.approx(truth["run_total_h"][day.device], abs=1e-5)
        assert day.starts_total == truth["starts_total"][day.device]


def test_alarm_activations_match(day_report: DailyReport, truth: dict[str, Any]) -> None:
    by_code = {}
    for event in day_report.events:
        by_code[f"{event.device}:{event.slot}@{event.ts.astimezone(MSK):%H:%M:%S}"] = event
    expected = [a for ref in truth["hours"] for a in ref["alarms"]]
    assert sorted(by_code) == sorted(expected)
    for row, ref in zip(day_report.hours, truth["hours"], strict=True):
        assert row.alarms_total == len(ref["alarms"])
    codes = [e.code for e in day_report.events]
    assert {"P102.FTS", "LT101.H", "LT101.HH", "ZS404.ALM"} <= set(codes)
    assert day_report.alarms_by_priority["High"] == sum(1 for e in day_report.events if e.priority == "High")


def test_level_within_publish_deadband(day_report: DailyReport, truth: dict[str, Any]) -> None:
    for row, ref in zip(day_report.hours, truth["hours"], strict=True):
        assert row.level_min_m is not None and row.level_max_m is not None and row.level_avg_m is not None
        assert row.level_min_m == pytest.approx(ref["level_min_m"], abs=LEVEL_TOLERANCE_M), ref["hour"]
        assert row.level_max_m == pytest.approx(ref["level_max_m"], abs=LEVEL_TOLERANCE_M), ref["hour"]
        assert row.level_min_m <= row.level_avg_m <= row.level_max_m


def test_gap_hour_coverage(day_report: DailyReport) -> None:
    coverage = [round(row.coverage, 3) for row in day_report.hours]
    assert 0.5 < coverage[GAP_HOUR] < 0.8
    assert all(c == 1.0 for i, c in enumerate(coverage) if i != GAP_HOUR)
    assert day_report.coverage == pytest.approx((23 + coverage[GAP_HOUR]) / 24, abs=1e-3)
