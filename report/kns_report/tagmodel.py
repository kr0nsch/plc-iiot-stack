"""Модель тегов флагмана КНС-1: теги SCADA и тревоги из файлов генератора iolistgen.

Файлы `data/scada_tags.csv` и `data/scada_alarms.csv` — копия вывода iolistgen флагмана
(kns-pump-station, `scada/*.csv`), та же, что `schema/source/` репозитория (совпадение проверяет
tests/test_tagmodel.py). Обновить: `python tools_project/flagship_snapshot.py` в корне репозитория и
скопировать `schema/source/scada_*.csv` в `report/kns_report/data/`.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

TAGS_FILE = "scada_tags.csv"
ALARMS_FILE = "scada_alarms.csv"


@dataclass(frozen=True)
class TagInfo:
    """Тег SCADA: имя `<DEV>.<свойство>`, путь в ПЛК и узел OPC UA."""

    tag: str
    description: str
    device: str
    device_type: str
    hmi_group: str
    data_type: str
    access: str
    units: str
    plc_path: str
    opcua_node_id: str
    alarm_hh: float | None = None
    alarm_h: float | None = None
    alarm_l: float | None = None
    alarm_ll: float | None = None


@dataclass(frozen=True)
class AlarmDef:
    """Тревога: id = dev_no · 10 + слот, код `<DEV>.<SUFFIX>`, бит slot в слове `<DEV>.AlmActive`."""

    id: int
    code: str
    device: str
    slot: int
    priority: str
    text: str


def _read_rows(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    return list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter=";"))


def _read_text(path: Path | None, name: str) -> str:
    if path is not None:
        return path.read_text(encoding="utf-8")
    return resources.files("kns_report").joinpath("data", name).read_text(encoding="utf-8")


def _opt_float(text: str) -> float | None:
    value = text.strip()
    return float(value.replace(",", ".")) if value else None


def load_tags(path: Path | None = None) -> dict[str, TagInfo]:
    """Теги SCADA по имени тега (по умолчанию — встроенная копия scada_tags.csv)."""
    result: dict[str, TagInfo] = {}
    for row in _read_rows(_read_text(path, TAGS_FILE)):
        info = TagInfo(
            tag=row["tag"],
            description=row["description"],
            device=row["device"],
            device_type=row["device_type"],
            hmi_group=row["hmi_group"],
            data_type=row["data_type"],
            access=row["access"],
            units=row["units"],
            plc_path=row["plc_path"],
            opcua_node_id=row["opcua_node_id"],
            alarm_hh=_opt_float(row["alarm_hh"]),
            alarm_h=_opt_float(row["alarm_h"]),
            alarm_l=_opt_float(row["alarm_l"]),
            alarm_ll=_opt_float(row["alarm_ll"]),
        )
        result[info.tag] = info
    return result


def load_alarms(path: Path | None = None) -> list[AlarmDef]:
    """Тревоги в порядке файла (по умолчанию — встроенная копия scada_alarms.csv)."""
    return [
        AlarmDef(
            id=int(row["id"]),
            code=row["code"],
            device=row["device"],
            slot=int(row["slot"]),
            priority=row["priority"],
            text=row["text"],
        )
        for row in _read_rows(_read_text(path, ALARMS_FILE))
    ]


def alarm_devices(alarms: list[AlarmDef]) -> list[str]:
    """Устройства, у которых есть тревоги, в порядке первого появления."""
    seen: dict[str, None] = {}
    for alarm in alarms:
        seen.setdefault(alarm.device, None)
    return list(seen)


def device_title(tags: dict[str, TagInfo], device: str) -> str:
    """Короткое имя устройства для заголовков: группа HMI насоса («Насос Н1») или тег."""
    for info in tags.values():
        if info.device == device and info.hmi_group:
            if info.hmi_group.lower().startswith("насос"):
                return info.hmi_group
            break
    return device
