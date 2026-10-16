"""Набор временных рядов по тегам SCADA и файл выборки (JSON Lines).

Файл выборки — одна строка JSON на опрос (так пишет источник OPC UA с --save-samples):

    {"ts": "2026-10-15T06:00:00Z", "values": {"LT101.Value": 2.31, "P101.Running": true}}

Допускается и «длинная» форма — строка на одно значение: {"ts": ..., "tag": ..., "value": ...}.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TextIO

from kns_report.timeutil import parse_rfc3339, to_rfc3339_utc

Value = float | int | bool
Point = tuple[datetime, Value]


@dataclass
class SeriesSet:
    """Ряды «тег → [(время, значение)]», отсортированные по времени."""

    series: dict[str, list[Point]] = field(default_factory=dict)

    def add(self, tag: str, ts: datetime, value: Value) -> None:
        if ts.tzinfo is None:
            raise ValueError(f"{tag}: отметка времени без пояса")
        self.series.setdefault(tag, []).append((ts, value))

    def sort(self) -> SeriesSet:
        for points in self.series.values():
            points.sort(key=lambda p: p[0])
        return self

    def get(self, tag: str) -> list[Point]:
        return self.series.get(tag, [])

    def tags(self) -> list[str]:
        return sorted(self.series)

    def time_range(self) -> tuple[datetime, datetime] | None:
        firsts = [p[0][0] for p in self.series.values() if p]
        lasts = [p[-1][0] for p in self.series.values() if p]
        if not firsts:
            return None
        return min(firsts), max(lasts)

    def horizon(self) -> datetime | None:
        """Граница выборки: последняя отметка плюс типичный шаг опроса (медиана по самому
        длинному ряду). Для файла выборки OPC UA — момент, до которого данные известны."""
        if not self.series:
            return None
        longest = max(self.series.values(), key=len)
        span = self.time_range()
        if span is None:
            return None
        steps = sorted((b[0] - a[0]) for a, b in itertools.pairwise(longest))
        step = steps[len(steps) // 2] if steps else timedelta(0)
        return span[1] + step

    def __len__(self) -> int:
        return sum(len(p) for p in self.series.values())

    def __iter__(self) -> Iterator[str]:
        return iter(self.series)


def _check_value(tag: str, value: object) -> Value:
    if isinstance(value, bool | int | float):
        return value
    raise ValueError(f"{tag}: значение {value!r} не число и не BOOL")


def load_jsonl(path: Path) -> SeriesSet:
    """Файл выборки → SeriesSet. Значения null пропускаются (нет данных)."""
    result = SeriesSet()
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            text = line.strip()
            if not text:
                continue
            try:
                record = json.loads(text)
                ts = parse_rfc3339(record["ts"])
                if "values" in record:
                    for tag, value in record["values"].items():
                        if value is not None:
                            result.add(tag, ts, _check_value(tag, value))
                elif record.get("value") is not None:
                    tag = str(record["tag"])
                    result.add(tag, ts, _check_value(tag, record["value"]))
            except (KeyError, ValueError, TypeError) as exc:
                raise ValueError(f"{path}:{number}: {exc}") from exc
    return result.sort()


def write_jsonl_record(handle: TextIO, ts: datetime, values: dict[str, Value | None]) -> None:
    """Одна строка файла выборки (handle — текстовый файл)."""
    line = json.dumps({"ts": to_rfc3339_utc(ts), "values": values}, ensure_ascii=False)
    handle.write(line + "\n")


def save_jsonl(records: Iterable[tuple[datetime, dict[str, Value | None]]], path: Path) -> None:
    """Опросы [(время, {тег: значение})] → файл выборки."""
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for ts, values in records:
            write_jsonl_record(handle, ts, values)
