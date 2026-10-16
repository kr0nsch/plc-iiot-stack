"""Общие фикстуры тестов kns-report (сеть не используется)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from kns_report.config import ReportConfig, load_config
from kns_report.tagmodel import AlarmDef, TagInfo, load_alarms, load_tags

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MSK = timezone(timedelta(hours=3))
GENERATED_AT = datetime(2026, 10, 16, 3, 0, tzinfo=UTC)


# Переменные стенда (.env), которые утилита читает из окружения. Юнит-тесты от них не зависят: в
# оболочке с загруженным .env (set -a; . ./.env) иначе подменялись бы токен, организация и адрес.
STAND_ENV = (
    "INFLUX_TOKEN",
    "INFLUX_ADMIN_TOKEN",
    "INFLUX_ORG",
    "INFLUX_BUCKET",
    "INFLUX_URL",
    "INFLUX_PORT",
    "DOCKER_INFLUXDB_INIT_ADMIN_TOKEN",
    "DOCKER_INFLUXDB_INIT_ORG",
    "DOCKER_INFLUXDB_INIT_BUCKET",
    "OPCUA_PASSWORD",
)


@pytest.fixture(autouse=True)
def _isolate_stand_env(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Окружение стенда — только для тестов с маркером integration (запросы к поднятой InfluxDB)."""
    if request.node.get_closest_marker("integration") is None:
        for name in STAND_ENV:
            monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="session")
def tags() -> dict[str, TagInfo]:
    return load_tags()


@pytest.fixture(scope="session")
def alarms() -> list[AlarmDef]:
    return load_alarms()


@pytest.fixture()
def cfg() -> ReportConfig:
    return load_config()


@pytest.fixture()
def strict_cfg(cfg: ReportConfig) -> ReportConfig:
    """Короткие интервалы удержания — удобно для ручных рядов в тестах агрегации."""
    station = replace(cfg.station, analog_max_gap=timedelta(minutes=10), discrete_max_gap=timedelta(hours=2))
    return replace(cfg, station=station)
