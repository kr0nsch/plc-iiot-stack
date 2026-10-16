"""CSV отчёта: почасовая таблица и список срабатываний тревог.

Формат как у остальных CSV проекта: UTF-8 без BOM, разделитель «;», десятичная точка,
заголовки — идентификаторы (ASCII). Пустая ячейка — нет данных за час. Для чтения человеком
предназначен XLSX.
"""

from __future__ import annotations

import csv
from pathlib import Path

from kns_report.aggregate import DailyReport
from kns_report.table import hourly_columns, rounded

DELIMITER = ";"


def write_hourly_csv(report: DailyReport, path: Path) -> None:
    columns = hourly_columns(report)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=DELIMITER, lineterminator="\n")
        writer.writerow([c.key for c in columns])
        for row in report.hours:
            cells = []
            for column in columns:
                value = rounded(column.get(row), column.digits)
                cells.append("" if value is None else value)
            writer.writerow(cells)


def write_alarms_csv(report: DailyReport, path: Path) -> None:
    tz = report.period_start.tzinfo
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=DELIMITER, lineterminator="\n")
        writer.writerow(["ts", "code", "device", "slot", "priority", "text"])
        for event in report.events:
            writer.writerow(
                [event.ts.astimezone(tz).isoformat(), event.code, event.device, event.slot, event.priority, event.text]
            )
