"""Настройки отчёта: встроенный default_config.toml плюс пользовательский файл и .env."""

from __future__ import annotations

import dataclasses
import os
import tomllib
from dataclasses import dataclass
from datetime import timedelta
from importlib import resources
from pathlib import Path
from typing import Any, TypeVar

from kns_report.timeutil import parse_duration

PUMP_METHODS = ("auto", "counters", "state")
ALARM_MODES = ("events", "words")


@dataclass(frozen=True)
class StationConfig:
    name: str
    site: str
    area: str
    timezone: str
    level_tag: str
    flow_tag: str
    pumps: tuple[str, ...]
    alarm_devices: tuple[str, ...]
    analog_max_gap: timedelta
    discrete_max_gap: timedelta
    pump_method: str


@dataclass(frozen=True)
class InfluxConfig:
    url: str
    org: str
    bucket: str
    token_env: str
    measurement: str
    field: str
    site_tag: str
    area_tag: str
    device_tag: str
    metric_tag: str
    source_tag: str
    source: str
    quality_field: str
    exclude_quality: tuple[str, ...]
    downsample: str
    timeout_s: float
    alarms: str
    alarm_measurement: str
    alarm_field: str
    alarm_value: str
    alarm_suffix_tag: str
    metrics: dict[str, str] = dataclasses.field(default_factory=dict)


@dataclass(frozen=True)
class OpcUaConfig:
    endpoint: str
    node_id_template: str
    ns_index: int
    namespace_uri: str
    device_name: str
    interval_s: float
    minutes: float
    user: str
    password_env: str
    security: str


@dataclass(frozen=True)
class ReportConfig:
    station: StationConfig
    influx: InfluxConfig
    opcua: OpcUaConfig


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _default_dict() -> dict[str, Any]:
    text = resources.files("kns_report").joinpath("default_config.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)


def _convert(name: str, annotation: str, value: Any) -> Any:
    if annotation == "timedelta":
        return parse_duration(str(value))
    if annotation == "tuple[str, ...]":
        if not isinstance(value, list):
            raise ValueError(f"{name}: ожидается список")
        return tuple(str(v) for v in value)
    if annotation == "dict[str, str]":
        if not isinstance(value, dict):
            raise ValueError(f"{name}: ожидается таблица")
        return {str(k): str(v) for k, v in value.items()}
    if annotation == "int":
        return int(value)
    if annotation == "float":
        return float(value)
    return str(value)


_T = TypeVar("_T")


def _section(cls: type[_T], name: str, data: dict[str, Any]) -> _T:
    fields = {f.name: f for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
    unknown = sorted(set(data) - set(fields))
    if unknown:
        raise ValueError(f"[{name}]: неизвестные ключи {', '.join(unknown)}")
    values = {}
    for key, spec in fields.items():
        if key not in data:
            if spec.default_factory is not dataclasses.MISSING:
                continue
            raise ValueError(f"[{name}]: нет ключа {key}")
        values[key] = _convert(f"[{name}] {key}", str(spec.type), data[key])
    return cls(**values)


def from_dict(data: dict[str, Any]) -> ReportConfig:
    """Настройки из словаря (структура как в default_config.toml) с проверкой ключей."""
    station = _section(StationConfig, "station", data["station"])
    if station.pump_method not in PUMP_METHODS:
        raise ValueError(f"[station] pump_method: {station.pump_method!r}, ожидается одно из {PUMP_METHODS}")
    influx = _section(InfluxConfig, "influx", data["influx"])
    if influx.alarms not in ALARM_MODES:
        raise ValueError(f"[influx] alarms: {influx.alarms!r}, ожидается одно из {ALARM_MODES}")
    opcua = _section(OpcUaConfig, "opcua", data["opcua"])
    return ReportConfig(station=station, influx=influx, opcua=opcua)


def load_config(path: Path | None = None) -> ReportConfig:
    """Встроенные настройки, поверх — файл path (если задан)."""
    data = _default_dict()
    if path is not None:
        with path.open("rb") as handle:
            data = _merge(data, tomllib.load(handle))
    return from_dict(data)


def read_env_file(path: Path) -> dict[str, str]:
    """Простой разбор .env: KEY=VALUE, комментарии #, кавычки вокруг значения снимаются."""
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        result[key.strip()] = value
    return result


def secret(name: str, env_file: dict[str, str] | None = None, *fallbacks: str) -> str | None:
    """Секрет из окружения (приоритет) или .env; fallbacks — запасные имена переменных."""
    for key in (name, *fallbacks):
        if not key:
            continue
        value = os.environ.get(key)
        if value:
            return value
        if env_file and env_file.get(key):
            return env_file[key]
    return None
