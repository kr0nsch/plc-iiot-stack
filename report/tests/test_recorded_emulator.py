"""Отчёт по настоящей записи OPC UA: kns-report opcua против эмулятора проекта.

tests/fixtures/opcua_emulator_recorded.jsonl записан командой

    kns-report opcua --endpoint opc.tcp://127.0.0.1:48410 --minutes 4 --interval 2 --save-samples ...

с эмулятора emulator/ (модельное время 1:1, анонимное чтение, 16.10.2026): 121 опрос, за это время
насос Н1 пустился один раз. Тест сверяет отчёт с расчётом «вручную» по тем же строкам файла и
два независимых метода моточасов (счётчик ПЛК и время с Running = TRUE).
"""

from __future__ import annotations

import itertools
import json
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

import pytest

from kns_report.aggregate import DailyReport, build_report
from kns_report.config import ReportConfig
from kns_report.samples import load_jsonl
from kns_report.tagmodel import AlarmDef, TagInfo
from kns_report.timeutil import ceil_hour, floor_hour, parse_rfc3339

from .conftest import FIXTURES, GENERATED_AT, MSK

RECORDING = FIXTURES / "opcua_emulator_recorded.jsonl"
POLL_S = 2.0


@pytest.fixture(scope="module")
def frames() -> list[dict[str, Any]]:
    return [json.loads(line) for line in RECORDING.read_text(encoding="utf-8").splitlines()]


def _report(cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef], method: str) -> DailyReport:
    series = load_jsonl(RECORDING)
    span = series.time_range()
    assert span is not None
    station = replace(cfg.station, pump_method=method)
    start, end = floor_hour(span[0], MSK), ceil_hour(span[1], MSK)
    return build_report(series, station, tags, alarms, start, end, "запись", GENERATED_AT, series.horizon())


def test_recording_shape(frames: list[dict[str, Any]], tags: dict[str, TagInfo]) -> None:
    assert len(frames) == 121
    times = [parse_rfc3339(f["ts"]) for f in frames]
    steps = [(b - a).total_seconds() for a, b in itertools.pairwise(times)]
    assert all(1.5 < s < 2.5 for s in steps)  # опрос по монотонным часам, без дрейфа
    assert set(frames[0]["values"]) <= set(tags)


def test_report_matches_manual_calculation(
    frames: list[dict[str, Any]], cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]
) -> None:
    report = _report(cfg, tags, alarms, "auto")
    assert len(report.hours) == 1
    hour = report.hours[0]
    times = [parse_rfc3339(f["ts"]) for f in frames]
    flows = [float(f["values"]["FT202.Value"]) for f in frames]
    levels = [float(f["values"]["LT101.Value"]) for f in frames]
    ends: list[datetime] = [*times[1:], times[-1] + timedelta(seconds=POLL_S)]
    volume = sum(q * (b - a).total_seconds() / 3600.0 for q, a, b in zip(flows, times, ends, strict=True))
    assert hour.volume_m3 == pytest.approx(volume, rel=1e-3)
    assert volume > 1.0  # насос работал
    assert hour.level_min_m == pytest.approx(min(levels))
    assert hour.level_max_m == pytest.approx(max(levels))
    span_s = (times[-1] - times[0]).total_seconds() + POLL_S
    assert hour.coverage == pytest.approx(span_s / 3600.0, rel=0.01)
    assert hour.alarms_total == 0 and report.events == []
    p101 = report.pumps[0]
    assert (p101.device, p101.run_method, p101.starts_method) == ("P101", "counters", "counters")
    assert p101.starts == 1
    assert p101.run_h == pytest.approx(frames[-1]["values"]["P101.RunTime"] - frames[0]["values"]["P101.RunTime"])


def test_counter_and_state_methods_agree(cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]) -> None:
    by_counters = _report(cfg, tags, alarms, "counters").pumps
    by_state = _report(cfg, tags, alarms, "state").pumps
    for ctr, state in zip(by_counters, by_state, strict=True):
        assert ctr.starts == state.starts
        assert ctr.run_h is not None and state.run_h is not None
        assert abs(ctr.run_h - state.run_h) * 3600.0 <= 2 * POLL_S  # расхождение не больше двух опросов
