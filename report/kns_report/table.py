"""Колонки почасовой таблицы — общие для CSV и XLSX."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from kns_report.aggregate import DailyReport, HourRow

Cell = float | int | str | None


@dataclass(frozen=True)
class Column:
    key: str  # заголовок CSV (идентификатор)
    title: str  # заголовок XLSX
    kind: str  # time | level | volume | hours | count | alarm | alarm_high | pct
    digits: int
    get: Callable[[HourRow], Cell]


def _pump_run(pump: str) -> Callable[[HourRow], Cell]:
    return lambda row: row.pumps[pump].run_h


def _pump_starts(pump: str) -> Callable[[HourRow], Cell]:
    return lambda row: row.pumps[pump].starts


def _alarms(bucket: str) -> Callable[[HourRow], Cell]:
    return lambda row: row.alarms_by_priority.get(bucket, 0)


def hourly_columns(report: DailyReport) -> list[Column]:
    columns = [
        Column("hour_start", "Час", "time", 0, lambda r: r.start.isoformat()),
        Column("level_min_m", "Уровень мин., м", "level", 3, lambda r: r.level_min_m),
        Column("level_avg_m", "Уровень ср., м", "level", 3, lambda r: r.level_avg_m),
        Column("level_max_m", "Уровень макс., м", "level", 3, lambda r: r.level_max_m),
        Column("volume_m3", "Откачано, м³", "volume", 2, lambda r: r.volume_m3),
    ]
    for pump in report.pumps:
        short = pump.title.replace("Насос ", "")
        key = pump.device.lower()
        columns.append(Column(f"{key}_run_h", f"{short}: работа, ч", "hours", 3, _pump_run(pump.device)))
        columns.append(Column(f"{key}_starts", f"{short}: пуски", "count", 0, _pump_starts(pump.device)))
    columns += [
        Column("alarms_total", "Тревог всего", "alarm", 0, lambda r: r.alarms_total),
        Column("alarms_high", "из них High", "alarm_high", 0, _alarms("High")),
        Column("alarms_medium", "Medium", "count", 0, _alarms("Medium")),
        Column("alarms_low", "Low", "count", 0, _alarms("Low")),
        Column("data_coverage_pct", "Полнота данных", "pct", 1, lambda r: r.coverage * 100.0),
    ]
    return columns


def rounded(value: Cell, digits: int) -> Cell:
    if isinstance(value, float):
        return round(value, digits) if digits else round(value)
    return value
