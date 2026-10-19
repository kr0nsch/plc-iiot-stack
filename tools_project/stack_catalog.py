"""Контракт данных стенда: каталог телеметрии, белый список команд, тревоги и топики.

Назначение: единственное место, где читаются файлы ``schema/`` (docs/data_schema.md). Модуль
используют генератор конфигурации (``gen_config.py``) и тесты согласованности (``tests_stack/``).
Автор: kr0nsch. Версия схемы данных: 1.0.

Источники:
- ``schema/telemetry_catalog.csv`` — метрики телеметрии (решение схемы данных);
- ``schema/command_whitelist.csv`` — команды, разрешённые по MQTT;
- ``schema/topics.json`` — грамматика топиков и параметры станции;
- ``schema/source/scada_tags.csv``, ``scada_alarms.csv`` — выход iolistgen по перечню сигналов
  флагмана КНС-1, ``station_tags.csv``, ``station_alarms.csv`` — теги и тревоги станции и регулятора
  LIC101 флагмана (все четыре пишет ``flagship_snapshot.py``, вручную не редактируются).
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO / "schema"

# Виды метрик каталога (раздел 3 docs/data_schema.md)
KINDS = ("analog", "discrete", "enum", "counter", "integer")
VALUE_TYPES = ("pulse", "number")
PRIORITIES = ("Low", "Medium", "High", "Critical")

# Измерения InfluxDB, которые пишет Telegraf (telegraf/telegraf.conf и telegraf.d/opcua.conf)
MEASUREMENTS = ("telemetry", "alarm", "command", "command_ack", "node_status")


@dataclass(frozen=True)
class Metric:
    """Строка каталога телеметрии: одна метрика — один топик."""

    device: str
    metric: str
    scada_tag: str
    kind: str
    unit: str
    deadband: float | None
    eng_min: float | None
    eng_max: float | None
    plc_path: str
    invert: bool  # значение метрики обратно сигналу ПЛК (0/1): K1 в норме под напряжением
    description: str


@dataclass(frozen=True)
class WhitelistEntry:
    """Команда, разрешённая устройству по MQTT."""

    device: str
    command: str
    value_type: str
    min: float | None
    max: float | None
    unit: str
    scada_tag: str
    plc_path: str


@dataclass(frozen=True)
class Alarm:
    """Тревога флагмана: устройства (iolistgen, id = dev_no * 10 + слот) или станции (id = 100000 + slot)."""

    id: int
    code: str
    device: str
    slot: int
    bit: int  # бит в словах тревог: у устройств = slot, у станции = slot - 1
    priority: str
    text: str
    setpoint: float | None
    delay_s: float


@dataclass(frozen=True)
class ScadaTag:
    """Строка scada_tags.csv (iolistgen) или station_tags.csv (теги станции того же формата)."""

    tag: str
    description: str
    device: str
    device_type: str
    data_type: str
    access: str
    units: str
    eng_min: float | None
    eng_max: float | None
    alarm_hh: float | None
    alarm_h: float | None
    alarm_l: float | None
    alarm_ll: float | None
    plc_path: str
    opcua_node_id: str


def _opt_float(text: str) -> float | None:
    text = text.strip().replace(",", ".")
    return float(text) if text else None


def read_semicolon_csv(path: Path) -> list[dict[str, str]]:
    """CSV с разделителем «;» и строками-комментариями «#» (формат iolistgen)."""
    raw = path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if line and not line.startswith("#")]
    return list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter=";"))


def load_catalog(root: Path = REPO) -> tuple[Metric, ...]:
    rows = read_semicolon_csv(root / "schema" / "telemetry_catalog.csv")
    return tuple(
        Metric(
            device=r["device"].strip(),
            metric=r["metric"].strip(),
            scada_tag=r["scada_tag"].strip(),
            kind=r["kind"].strip(),
            unit=r["unit"].strip(),
            deadband=_opt_float(r["deadband"]),
            eng_min=_opt_float(r["eng_min"]),
            eng_max=_opt_float(r["eng_max"]),
            plc_path=r["plc_path"].strip(),
            invert=r["invert"].strip() == "1",
            description=r["description"].strip(),
        )
        for r in rows
    )


def load_whitelist(root: Path = REPO) -> tuple[WhitelistEntry, ...]:
    rows = read_semicolon_csv(root / "schema" / "command_whitelist.csv")
    return tuple(
        WhitelistEntry(
            device=r["device"].strip(),
            command=r["command"].strip(),
            value_type=r["value_type"].strip(),
            min=_opt_float(r["min"]),
            max=_opt_float(r["max"]),
            unit=r["unit"].strip(),
            scada_tag=r["scada_tag"].strip(),
            plc_path=r["plc_path"].strip(),
        )
        for r in rows
    )


ALARM_FILES = ("scada_alarms.csv", "station_alarms.csv")
TAG_FILES = ("scada_tags.csv", "station_tags.csv")


def load_alarms(root: Path = REPO) -> tuple[Alarm, ...]:
    """Тревоги устройств, затем тревоги станции (порядок файлов)."""
    rows = [r for name in ALARM_FILES for r in read_semicolon_csv(root / "schema" / "source" / name)]
    return tuple(
        Alarm(
            id=int(r["id"]),
            code=r["code"].strip(),
            device=r["device"].strip(),
            slot=int(r["slot"]),
            bit=int(r["bit"]),
            priority=r["priority"].strip(),
            text=r["text"].strip(),
            setpoint=_opt_float(r["setpoint"]),
            delay_s=_opt_float(r["delay_s"]) or 0.0,
        )
        for r in rows
    )


def load_scada_tags(root: Path = REPO) -> tuple[ScadaTag, ...]:
    """Теги устройств (iolistgen), затем теги станции и LIC101."""
    rows = [r for name in TAG_FILES for r in read_semicolon_csv(root / "schema" / "source" / name)]
    return tuple(
        ScadaTag(
            tag=r["tag"].strip(),
            description=r["description"].strip(),
            device=r["device"].strip(),
            device_type=r["device_type"].strip(),
            data_type=r["data_type"].strip(),
            access=r["access"].strip(),
            units=r["units"].strip(),
            eng_min=_opt_float(r["eng_min"]),
            eng_max=_opt_float(r["eng_max"]),
            alarm_hh=_opt_float(r["alarm_hh"]),
            alarm_h=_opt_float(r["alarm_h"]),
            alarm_l=_opt_float(r["alarm_l"]),
            alarm_ll=_opt_float(r["alarm_ll"]),
            plc_path=r["plc_path"].strip(),
            opcua_node_id=r["opcua_node_id"].strip(),
        )
        for r in rows
    )


def load_topics(root: Path = REPO) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((root / "schema" / "topics.json").read_text(encoding="utf-8"))
    return data


def load_schema(name: str, root: Path = REPO) -> dict[str, Any]:
    """JSON Schema класса сообщений: telemetry, alarm, command, command_ack, status."""
    data: dict[str, Any] = json.loads((root / "schema" / f"{name}.schema.json").read_text(encoding="utf-8"))
    return data


def station(root: Path = REPO) -> dict[str, str]:
    """site, area, unit и имя узла ПЛК станции."""
    st: dict[str, str] = load_topics(root)["station"]
    return st


def telemetry_topic(m: Metric, root: Path = REPO) -> str:
    st = station(root)
    return f"{st['site']}/{st['area']}/{st['unit']}/{m.device}/{m.metric}"


def classify_topic(topic: str, root: Path = REPO) -> tuple[str, dict[str, str]] | None:
    """Класс топика и его уровни по schema/topics.json; None — топик вне соглашения."""
    for name, cls in load_topics(root)["classes"].items():
        match = re.fullmatch(cls["pattern"], topic)
        if match:
            return name, dict(zip(cls["groups"], match.groups(), strict=True))
    return None


def alarm_limits(device: str, root: Path = REPO) -> dict[str, tuple[float, str]]:
    """Уставки тревог аналогового устройства: суффикс (HH, H, L, LL) → (уставка, приоритет)."""
    out: dict[str, tuple[float, str]] = {}
    for a in load_alarms(root):
        suffix = a.code.split(".", 1)[1]
        if a.device == device and suffix in ("HH", "H", "L", "LL") and a.setpoint is not None:
            out[suffix] = (a.setpoint, a.priority)
    return out
