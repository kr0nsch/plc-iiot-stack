"""Время: часовые пояса, границы суток и часов, формат RFC 3339.

Все отметки времени внутри пакета — aware datetime. Часы отчёта нарезаются шагом ровно 1 ч от
начала периода; для поясов с фиксированным смещением (МСК = UTC+3, переходов нет с 2014 г.)
это и есть местные часы.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo

HOUR = timedelta(hours=1)

_OFFSET_RE = re.compile(r"^(?:UTC)?([+-])(\d{1,2})(?::?(\d{2}))?$")
# Дробная часть секунд InfluxDB — до 9 знаков; datetime хранит 6
_FRACTION_RE = re.compile(r"(\.\d{6})\d+")


def parse_tz(name: str) -> tzinfo:
    """Пояс по имени: "UTC", смещение "+03:00" / "UTC+3" или имя IANA ("Europe/Moscow").

    Имена IANA на Windows требуют пакет tzdata (pip install tzdata).
    """
    text = name.strip()
    if text.upper() in ("UTC", "Z"):
        return UTC
    match = _OFFSET_RE.match(text.upper())
    if match:
        sign = -1 if match.group(1) == "-" else 1
        hours = int(match.group(2))
        minutes = int(match.group(3) or 0)
        if hours > 23 or minutes > 59:
            raise ValueError(f"недопустимое смещение пояса: {name!r}")
        return timezone(sign * timedelta(hours=hours, minutes=minutes))
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError as exc:  # pragma: no cover - zoneinfo есть в 3.9+
        raise ValueError(f"пояс {name!r}: модуль zoneinfo недоступен") from exc
    try:
        return ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"неизвестный часовой пояс {name!r}; задайте смещение (+03:00) или установите tzdata") from exc


def day_bounds(day: date, tz: tzinfo) -> tuple[datetime, datetime]:
    """Начало и конец местных суток day (конец не включается)."""
    start = datetime.combine(day, time(0, 0), tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=tz)
    return start, end


def floor_hour(ts: datetime, tz: tzinfo) -> datetime:
    """Начало местного часа, в который попадает ts."""
    local = ts.astimezone(tz)
    return local.replace(minute=0, second=0, microsecond=0)


def ceil_hour(ts: datetime, tz: tzinfo) -> datetime:
    """Ближайшая граница местного часа не раньше ts."""
    start = floor_hour(ts, tz)
    return start if start == ts.astimezone(tz) else start + HOUR


def hour_starts(start: datetime, end: datetime) -> list[datetime]:
    """Начала часов [start, end) с шагом ровно 1 ч физического времени (в поясе start)."""
    if end <= start:
        return []
    tz = start.tzinfo
    result = []
    current = start.astimezone(UTC)
    stop = end.astimezone(UTC)
    while current < stop:
        result.append(current.astimezone(tz))
        current = current + HOUR
    return result


def parse_rfc3339(text: str) -> datetime:
    """RFC 3339 из InfluxDB ("2026-10-14T21:00:05.123456789Z") → aware datetime."""
    value = text.strip()
    if value.endswith(("Z", "z")):
        value = value[:-1] + "+00:00"
    value = _FRACTION_RE.sub(r"\1", value)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"отметка времени без пояса: {text!r}")
    return parsed


def to_rfc3339_utc(ts: datetime) -> str:
    """Aware datetime → "2026-10-14T21:00:00Z" (для Flux и файлов выборки)."""
    if ts.tzinfo is None:
        raise ValueError("ожидается aware datetime")
    utc = ts.astimezone(UTC)
    if utc.microsecond:
        return utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_duration(text: str) -> timedelta:
    """Длительность "90s", "10m", "2h", "1h30m" или число секунд."""
    value = text.strip().lower()
    if not value:
        raise ValueError("пустая длительность")
    if re.fullmatch(r"\d+(\.\d+)?", value):
        return timedelta(seconds=float(value))
    parts = re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h|d)", value)
    if not parts or "".join(n + u for n, u in parts) != value:
        raise ValueError(f"недопустимая длительность: {text!r}")
    factor = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}
    return timedelta(seconds=sum(float(n) * factor[u] for n, u in parts))
