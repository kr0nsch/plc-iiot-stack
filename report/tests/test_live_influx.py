"""Проверка на поднятом стенде (по желанию): запросы Flux утилиты выполняются настоящей InfluxDB.

Пропускается, если не задан KNS_REPORT_INFLUX_URL. На стенде после `make demo` (bash):

    set -a; . ./.env; set +a
    KNS_REPORT_INFLUX_URL=http://localhost:8086 python -m pytest report/tests -m integration

Токен (INFLUX_TOKEN или INFLUX_ADMIN_TOKEN стенда), организация и бакет (INFLUX_ORG, INFLUX_BUCKET) — из окружения.
"""

from __future__ import annotations

import csv
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kns_report import cli

pytestmark = pytest.mark.integration

MSK_OFFSET = timedelta(hours=3)


def test_live_influx_today(tmp_path: Path) -> None:
    url = os.environ.get("KNS_REPORT_INFLUX_URL")
    if not url or not (os.environ.get("INFLUX_TOKEN") or os.environ.get("INFLUX_ADMIN_TOKEN")):
        pytest.skip("нет KNS_REPORT_INFLUX_URL или токена InfluxDB: стенд не поднят")
    today = (datetime.now(UTC) + MSK_OFFSET).date().isoformat()
    argv = ["influx", "--url", url, "--date", today, "--out-dir", str(tmp_path), "--formats", "csv,xlsx"]
    for option, variable in (("--org", "INFLUX_ORG"), ("--bucket", "INFLUX_BUCKET")):
        if os.environ.get(variable):
            argv += [option, os.environ[variable]]
    assert cli.main(argv) == 0
    rows = list(csv.DictReader((tmp_path / f"kns1_daily_{today}.csv").open(encoding="utf-8"), delimiter=";"))
    assert len(rows) == 24
    assert any(r["level_avg_m"] for r in rows), "за сегодня нет ни одного значения уровня"
    assert (tmp_path / f"kns1_daily_{today}.xlsx").exists()
