"""Схема данных MQTT стенда в коде эмулятора: топики, каталог телеметрии, белый список, сообщения.

Контракт — файлы ``schema/`` репозитория (topics.json, telemetry_catalog.csv,
command_whitelist.csv, ``*.schema.json``; описание — docs/data_schema.md). Эмулятор хранит копии
CSV и topics.json в ``iiot_emulator/data/`` (образ Docker собирается без остального
репозитория); тест ``test_schema_copies_match_repo`` следит, чтобы копии не разошлись.

Схемы JSON эмулятор во время работы не загружает: сообщения строятся здесь, а тесты проверяют
каждый вид сообщения по ``schema/*.schema.json``.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any

SCHEMA_VERSION = "1.0"
SCHEMA_MAJOR = 1

# E_AlarmState, E_AlarmEventReason, E_AlarmPriority, E_CmdResult → строки схемы
ALARM_STATE_NAMES = ("Normal", "ActiveUnack", "ActiveAck", "RtnUnack", "Shelved", "SuppressedByDesign", "OutOfService")
ALARM_REASON_NAMES = (
    "None",
    "Activated",
    "Cleared",
    "Acked",
    "Shelved",
    "Unshelved",
    "ShelveExpired",
    "Suppressed",
    "Unsuppressed",
    "OosOn",
    "OosOff",
)
PRIORITY_NAMES = ("None", "Low", "Medium", "High", "Critical")
CMD_RESULT_NAMES = (
    "None",
    "Accepted",
    "RejectedMode",
    "RejectedInterlock",
    "RejectedPermit",
    "RejectedInhibit",
    "RejectedFault",
    "RejectedState",
    "RejectedNotSupported",
    "RejectedCfg",
    "SubstExpired",
)

# Причины отказа в cmd_ack (command_ack.schema.json)
ACK_REASONS = (
    "ok",
    "not_whitelisted",
    "out_of_range",
    "invalid_payload",
    "unsupported_version",
    "topic_mismatch",
    "retained",
    "expired",
    "duplicate",
    "rate_limited",
    "device_rejected",
    "timeout",
)

# Команды схемы (command.schema.json, поле command) и где у них значение
COMMANDS = (
    "SetAuto",
    "SetManual",
    "SetOos",
    "Start",
    "Stop",
    "SpeedSp",
    "ResetMaint",
    "SubstValue",
    "Ack",
    "Reset",
    "AckReq",
    "ShelveReq",
    "UnshelveReq",
)
VALUE_COMMANDS = frozenset({"SpeedSp", "SubstValue"})
MASK_COMMANDS = frozenset({"AckReq", "ShelveReq", "UnshelveReq"})


def _data_text(name: str) -> str:
    return resources.files("iiot_emulator").joinpath("data", name).read_text(encoding="utf-8")


def _csv_rows(name: str) -> list[dict[str, str]]:
    lines = [line for line in _data_text(name).splitlines() if line and not line.startswith("#")]
    return list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter=";"))


def _opt_float(text: str) -> float | None:
    text = text.strip().replace(",", ".")
    return float(text) if text else None


@dataclass(frozen=True)
class Metric:
    """Строка telemetry_catalog.csv: одна метрика — один топик."""

    device: str
    metric: str
    scada_tag: str  # пусто у диагностики узла (PLC1)
    kind: str  # analog | discrete | enum | counter | integer
    unit: str
    deadband: float | None
    eng_min: float | None
    eng_max: float | None


@dataclass(frozen=True)
class WhitelistEntry:
    """Строка command_whitelist.csv."""

    device: str
    command: str
    value_type: str  # pulse | number
    min: float | None
    max: float | None
    scada_tag: str


@dataclass(frozen=True)
class Topics:
    """Уровни топиков станции (topics.json → station) и построение топиков."""

    site: str
    area: str
    unit: str
    node: str

    @property
    def prefix(self) -> str:
        return f"{self.site}/{self.area}/{self.unit}"

    def telemetry(self, device: str, metric: str) -> str:
        return f"{self.prefix}/{device}/{metric}"

    def alarm(self, device: str, suffix: str) -> str:
        return f"{self.prefix}/{device}/alarm/{suffix}"

    def command_filter(self) -> str:
        return f"{self.prefix}/+/cmd/+"

    def command_ack(self, device: str, command: str) -> str:
        return f"{self.prefix}/{device}/cmd_ack/{command}"

    def status(self) -> str:
        return f"{self.prefix}/{self.node}/status/connection"

    def parse_command_topic(self, topic: str) -> tuple[str, str] | None:
        """``<prefix>/<device>/cmd/<command>`` → (device, command) или None."""
        parts = topic.split("/")
        if len(parts) != 6 or "/".join(parts[:3]) != self.prefix or parts[4] != "cmd":
            return None
        return parts[3], parts[5]


@cache
def topics_config() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_data_text("topics.json"))
    return data


def default_topics() -> Topics:
    st = topics_config()["station"]
    return Topics(site=st["site"], area=st["area"], unit=st["unit"], node=st["node"])


@cache
def telemetry_catalog() -> tuple[Metric, ...]:
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
        )
        for r in _csv_rows("telemetry_catalog.csv")
    )


@cache
def command_whitelist() -> dict[tuple[str, str], WhitelistEntry]:
    out: dict[tuple[str, str], WhitelistEntry] = {}
    for r in _csv_rows("command_whitelist.csv"):
        e = WhitelistEntry(
            device=r["device"].strip(),
            command=r["command"].strip(),
            value_type=r["value_type"].strip(),
            min=_opt_float(r["min"]),
            max=_opt_float(r["max"]),
            scada_tag=r["scada_tag"].strip(),
        )
        out[(e.device, e.command)] = e
    return out


# --- сообщения ------------------------------------------------------------------------------------
def quality_from_ne107(ne107: int, valid: bool = True) -> str:
    """NE 107 устройства → quality телеметрии (docs/data_schema.md, раздел 3.2).

    bad — Failure; uncertain — CheckFunction (подмена, вывод из работы) или OutOfSpecification;
    bad — значение недостоверно (``xValid = FALSE``) при прочих статусах; good — Good или
    MaintenanceRequired с достоверным значением.
    """
    if ne107 >= 4:
        return "bad"
    if ne107 in (2, 3):
        return "uncertain"
    return "good" if valid else "bad"


def telemetry_payload(ts_ms: int, value: float | int, quality: str, unit: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "ts": ts_ms, "value": value, "quality": quality}
    if unit:
        payload["unit"] = unit
    return payload


def alarm_payload(
    ts_ms: int,
    alarm_id: int,
    code: str,
    priority: int,
    state: int,
    prev_state: int,
    reason: int,
    value: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ts": ts_ms,
        "id": alarm_id,
        "code": code,
        "priority": PRIORITY_NAMES[priority],
        "state": ALARM_STATE_NAMES[state],
        "prev_state": ALARM_STATE_NAMES[prev_state],
        "reason": ALARM_REASON_NAMES[reason],
    }
    if value is not None:
        payload["value"] = round(float(value), 4)
    return payload


def ack_payload(ts_ms: int, cmd_id: str, command: str, reason: str, cmd_result: int | None = None) -> dict[str, Any]:
    if reason not in ACK_REASONS:
        raise ValueError(f"неизвестная причина {reason!r}")
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "cmd_id": cmd_id,
        "ts": ts_ms,
        "command": command,
        "result": "accepted" if reason == "ok" else "rejected",
        "reason": reason,
    }
    if cmd_result is not None and 0 < cmd_result < len(CMD_RESULT_NAMES) - 1:
        payload["cmd_result"] = CMD_RESULT_NAMES[cmd_result]
    return payload


def status_payload(
    ts_ms: int, node: str, online: bool, reason: str, *, sw_version: str = "", period_ms: int | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ts": ts_ms,
        "node": node,
        "state": "online" if online else "offline",
        "reason": reason,
        "source": "emulator",
    }
    if sw_version:
        payload["sw_version"] = sw_version
    if period_ms is not None:
        payload["period_ms"] = period_ms
    return payload


def dumps(payload: dict[str, Any]) -> bytes:
    """Компактный JSON в UTF-8 (так же публикует ПЛК: без пробелов)."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
