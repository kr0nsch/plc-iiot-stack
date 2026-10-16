"""Модель тегов КНС-1: перечень тегов SCADA и тревог, сгенерированный iolistgen.

Источник истины — перечень сигналов флагмана (проект 02, ``io_list.csv``). Из него генератор
``iolistgen`` (проект 07) строит ``scada_tags.csv`` и ``scada_alarms.csv``; копии лежат в
``iiot_emulator/data/``. Эмулятор не придумывает теги: узлы OPC UA, типы данных и права доступа
берутся из этих файлов, поэтому клиент (Telegraf, отчёт, сценарии ПМИ) работает с эмулятором и
с настоящим рантаймом CODESYS одинаково.

Обновить копии: ``python -m iolistgen generate examples/kns/io_list.csv --out <каталог>`` в
репозитории iolistgen и скопировать ``scada/*.csv`` сюда.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from functools import cache
from importlib import resources

# Типы IEC 61131-3, которые встречаются в перечне, и их диапазоны (для проверки команд)
IEC_INT_RANGES: dict[str, tuple[int, int]] = {
    "INT": (-32768, 32767),
    "UINT": (0, 65535),
    "WORD": (0, 65535),
    "DINT": (-(2**31), 2**31 - 1),
    "UDINT": (0, 2**32 - 1),
    "DWORD": (0, 2**32 - 1),
}
IEC_TYPES = frozenset({"BOOL", "REAL", "LREAL", *IEC_INT_RANGES})

# Префикс узлов символьной конфигурации CODESYS: так их показывает scada_tags.csv
DEFAULT_DEVICE_NAME = "CODESYS Control Win V3"
DEFAULT_SYMBOL_NS = 4


@dataclass(frozen=True)
class TagDef:
    """Тег SCADA: строка scada_tags.csv."""

    tag: str  # P101.Cmd.Start, LT101.Value, HA1
    description: str
    device: str  # P101; пусто у сигналов без ФБ (AUX)
    dev_no: int | None
    device_type: str  # MotorVfd, Motor, AnalogInput, DigitalInput; пусто у AUX
    hmi_group: str
    data_type: str  # BOOL, INT, WORD, UINT, UDINT, REAL
    writable: bool  # access RW — команда HMI/SCADA (GVL_Hmi)
    units: str
    eng_min: float | None
    eng_max: float | None
    alarm_hh: float | None
    alarm_h: float | None
    alarm_l: float | None
    alarm_ll: float | None
    alarm_priority: str
    plc_path: str  # Application.GVL_Devices.fbLT101.stSts.rValue_eu
    opcua_node_id: str  # ns=4;s=|var|CODESYS Control Win V3.Application....

    @property
    def key(self) -> str:
        """Ключ внутри устройства: ``Value``, ``Cmd.Start``; у AUX — сам тег."""
        if self.device and self.tag.startswith(self.device + "."):
            return self.tag[len(self.device) + 1 :]
        return self.tag

    @property
    def is_command(self) -> bool:
        return self.writable

    @property
    def is_pulse(self) -> bool:
        """Импульсный бит команды: ПЛК сбрасывает его после обработки (API 2.1)."""
        return self.writable and self.data_type == "BOOL" and self.key.startswith("Cmd.") and not self.is_value_cmd

    @property
    def is_mask(self) -> bool:
        """Маска тревог (AckReq, ShelveReq, UnshelveReq): ПЛК обнуляет слово после обработки."""
        return self.writable and self.data_type == "WORD"

    @property
    def is_value_cmd(self) -> bool:
        """Значение команды (SpeedSp, SubstValue): ПЛК не сбрасывает, а в Auto пишет текущее."""
        return self.writable and self.key in ("Cmd.SpeedSp", "Cmd.SubstValue")

    def symbol_path(self) -> str:
        """Путь символа без префикса ``Application.``: ``GVL_Devices.fbLT101.stSts.rValue_eu``."""
        return self.plc_path.removeprefix("Application.")


@dataclass(frozen=True)
class AlarmDef:
    """Тревога устройства: строка scada_alarms.csv (id = dev_no · 10 + слот)."""

    id: int
    code: str  # LT101.HH
    device: str
    slot: int
    priority: str  # Low, Medium, High, Critical
    text: str
    setpoint: float | None
    delay_s: float


def _opt_float(text: str) -> float | None:
    text = text.strip().replace(",", ".")
    return float(text) if text else None


def _opt_int(text: str) -> int | None:
    text = text.strip()
    return int(text) if text else None


def _read_csv(name: str) -> list[dict[str, str]]:
    raw = resources.files("iiot_emulator").joinpath("data", name).read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if line and not line.startswith("#")]
    return list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter=";"))


@cache
def load_tags() -> tuple[TagDef, ...]:
    """Все теги перечня в порядке файла."""
    out: list[TagDef] = []
    for row in _read_csv("scada_tags.csv"):
        dtype = row["data_type"].strip()
        if dtype not in IEC_TYPES:
            raise ValueError(f"scada_tags.csv: неизвестный тип {dtype!r} у тега {row['tag']}")
        out.append(
            TagDef(
                tag=row["tag"].strip(),
                description=row["description"].strip(),
                device=row["device"].strip(),
                dev_no=_opt_int(row["dev_no"]),
                device_type=row["device_type"].strip(),
                hmi_group=row["hmi_group"].strip(),
                data_type=dtype,
                writable=row["access"].strip().upper() == "RW",
                units=row["units"].strip(),
                eng_min=_opt_float(row["eng_min"]),
                eng_max=_opt_float(row["eng_max"]),
                alarm_hh=_opt_float(row["alarm_hh"]),
                alarm_h=_opt_float(row["alarm_h"]),
                alarm_l=_opt_float(row["alarm_l"]),
                alarm_ll=_opt_float(row["alarm_ll"]),
                alarm_priority=row["alarm_priority"].strip(),
                plc_path=row["plc_path"].strip(),
                opcua_node_id=row["opcua_node_id"].strip(),
            )
        )
    return tuple(out)


@cache
def load_alarms() -> tuple[AlarmDef, ...]:
    """Все тревоги устройств в порядке файла."""
    return tuple(
        AlarmDef(
            id=int(row["id"]),
            code=row["code"].strip(),
            device=row["device"].strip(),
            slot=int(row["slot"]),
            priority=row["priority"].strip(),
            text=row["text"].strip(),
            setpoint=_opt_float(row["setpoint"]),
            delay_s=_opt_float(row["delay_s"]) or 0.0,
        )
        for row in _read_csv("scada_alarms.csv")
    )


@cache
def tags_by_name() -> dict[str, TagDef]:
    return {t.tag: t for t in load_tags()}


@cache
def devices() -> dict[str, tuple[str, int, str]]:
    """Устройства перечня: тег → (тип устройства, dev_no, группа HMI), в порядке файла."""
    out: dict[str, tuple[str, int, str]] = {}
    for t in load_tags():
        if t.device and t.device_type and t.dev_no is not None and t.device not in out:
            out[t.device] = (t.device_type, t.dev_no, t.hmi_group)
    return out


def alarms_of(device: str) -> list[AlarmDef]:
    return [a for a in load_alarms() if a.device == device]


def node_id_for(tag: TagDef, *, ns: int = DEFAULT_SYMBOL_NS, device_name: str = DEFAULT_DEVICE_NAME) -> str:
    """Идентификатор узла OPC UA в стиле CODESYS: ``ns=4;s=|var|<устройство>.Application.<путь>``.

    По умолчанию совпадает с колонкой opcua_node_id; номер пространства имён и имя устройства
    рантайма можно переопределить (у ПЛК210 имя устройства другое — сверить по обзору сервера).
    """
    return f"ns={ns};s=|var|{device_name}.{tag.plc_path}"
