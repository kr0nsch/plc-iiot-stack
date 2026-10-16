"""Часовые пояса, RFC 3339, длительности, нарезка часов."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from kns_report.timeutil import (
    ceil_hour,
    day_bounds,
    floor_hour,
    hour_starts,
    parse_duration,
    parse_rfc3339,
    parse_tz,
    to_rfc3339_utc,
)

MSK = timezone(timedelta(hours=3))


@pytest.mark.parametrize(
    ("text", "offset_h"),
    [("UTC", 0), ("+03:00", 3), ("UTC+3", 3), ("-05:30", -5.5), ("+0300", 3), ("z", 0)],
)
def test_parse_tz_offsets(text: str, offset_h: float) -> None:
    tz = parse_tz(text)
    assert tz.utcoffset(None) == timedelta(hours=offset_h)


def test_parse_tz_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="пояс"):
        parse_tz("Mars/Olympus")
    with pytest.raises(ValueError, match="смещение"):
        parse_tz("+25:00")


def test_rfc3339_nanoseconds_and_zulu() -> None:
    ts = parse_rfc3339("2026-10-14T21:00:05.123456789Z")
    assert ts == datetime(2026, 10, 14, 21, 0, 5, 123456, tzinfo=UTC)
    assert to_rfc3339_utc(ts) == "2026-10-14T21:00:05.123456Z"
    assert to_rfc3339_utc(datetime(2026, 10, 15, 0, 0, tzinfo=MSK)) == "2026-10-14T21:00:00Z"


def test_rfc3339_requires_zone() -> None:
    with pytest.raises(ValueError, match="без пояса"):
        parse_rfc3339("2026-10-14T21:00:00")


def test_day_bounds_and_hours_local() -> None:
    start, end = day_bounds(date(2026, 10, 15), MSK)
    hours = hour_starts(start, end)
    assert len(hours) == 24
    assert hours[0].isoformat() == "2026-10-15T00:00:00+03:00"
    assert hours[-1].isoformat() == "2026-10-15T23:00:00+03:00"
    assert hour_starts(end, start) == []


def test_floor_ceil_hour() -> None:
    ts = datetime(2026, 10, 15, 7, 10, 30, tzinfo=UTC)  # 10:10:30 МСК
    assert floor_hour(ts, MSK).isoformat() == "2026-10-15T10:00:00+03:00"
    assert ceil_hour(ts, MSK).isoformat() == "2026-10-15T11:00:00+03:00"
    exact = datetime(2026, 10, 15, 7, 0, tzinfo=UTC)
    assert ceil_hour(exact, MSK) == floor_hour(exact, MSK)


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("90", 90), ("90s", 90), ("10m", 600), ("2h", 7200), ("1h30m", 5400), ("500ms", 0.5), ("1d", 86400)],
)
def test_parse_duration(text: str, seconds: float) -> None:
    assert parse_duration(text).total_seconds() == seconds


@pytest.mark.parametrize("text", ["", "10x", "m10", "1h 30m"])
def test_parse_duration_rejects(text: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(text)
