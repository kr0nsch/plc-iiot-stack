"""Снимок интерфейса флагмана КНС-1 (kns-pump-station) для привязки IIoT-стека.

Назначение: взять из git флагмана (``git show <rev>:<путь>``, рабочая копия флагмана не меняется) то,
что нужно стенду, и записать в ``schema/source/``:

- ``scada_tags.csv``, ``scada_alarms.csv`` — теги и тревоги устройств, выход iolistgen флагмана
  (``scada/*.csv``), без изменений;
- ``station_tags.csv`` — теги станции и регулятора уровня в том же формате: ``KNS1.*`` —
  ``GVL_Station.stStationSts`` (чтение) и ``stStationCmd`` (запись), ``LIC101.*`` —
  ``GVL_Station.fbLIC101.stSts`` (чтение) и ``stLIC101Cmd`` (запись); типы — из объявлений флагмана и
  контракта plc-process-lib, права — из правил символьной конфигурации флагмана;
- ``station_alarms.csv`` — тревоги станции из ``docs/05_alarm_list.csv`` (``source = station``) в
  формате ``scada_alarms.csv``; бит в словах тревог станции — ``slot - 1``; тревоги с приоритетом
  None (выключены) не входят;
- ``flagship_symbols.json`` — коммит флагмана, SHA-256 исходных файлов, объявления глобальных списков,
  типы (структуры флагмана и plc-process-lib) и правила символьной конфигурации: по ним
  ``flagship_symbols.py`` проверяет любой путь ``Application.<GVL>.<…>`` — тип и доступ OPC UA.

Автор: kr0nsch. Документ: docs/ARCHITECTURE.md, раздел «Привязка к флагману».

Запуск из корня репозитория::

    python tools_project/flagship_snapshot.py                     # ../kns-pump-station, ветка main
    python tools_project/flagship_snapshot.py --rev 505ce14 --check
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "schema" / "source"
DEFAULT_FLAGSHIP = REPO.parent / "kns-pump-station"
TOOL = "tools_project/flagship_snapshot.py"

# Файлы флагмана, из которых строится снимок
SCADA_TAGS = "scada/scada_tags.csv"
SCADA_ALARMS = "scada/scada_alarms.csv"
ALARM_LIST = "docs/05_alarm_list.csv"
SYMBOL_RULES = "tools_project/codesys/symbol_rules.json"
PL_CONTRACT = "tools_project/data/plc_process_lib.json"
GVL_DIR = "src/GVLs"
DUT_DIR = "src/DUTs"

# Узел OPC UA рантайма CODESYS Control Win V3 (как колонка opcua_node_id iolistgen)
NODE_PREFIX = "ns=4;s=|var|CODESYS Control Win V3."
APP = "Application."

TAG_COLUMNS = (
    "tag",
    "description",
    "device",
    "dev_no",
    "device_type",
    "hmi_group",
    "data_type",
    "access",
    "units",
    "eng_min",
    "eng_max",
    "alarm_hh",
    "alarm_h",
    "alarm_l",
    "alarm_ll",
    "alarm_priority",
    "plc_path",
    "opcua_node_id",
)
ALARM_COLUMNS = (
    "id",
    "code",
    "device",
    "slot",
    "priority",
    "text",
    "active_tag",
    "unack_tag",
    "ack_tag",
    "bit",
    "setpoint",
    "delay_s",
)

ELEMENTARY = frozenset(
    {"BOOL", "BYTE", "WORD", "DWORD", "LWORD", "SINT", "USINT", "INT", "UINT", "DINT", "UDINT", "LINT", "ULINT"}
    | {"REAL", "LREAL", "TIME", "LTIME", "DATE", "TOD", "DT", "STRING", "WSTRING"}
)
UNITS = {"m": "м", "pct": "%", "s": "с", "ms": "мс", "h": "ч", "A": "А"}

# Порядок полей структур plc-process-lib (контракт хранит их по алфавиту): общий заголовок — как теги
# iolistgen, остальное — порядок объявлений библиотеки 1.0.0
PL_ORDER = {
    "ST_DeviceSts": (
        "eMode",
        "eNe107",
        "wStatus",
        "wFault",
        "wWarning",
        "wCfgErr",
        "wAlmActive",
        "wAlmUnack",
        "wAlmShelved",
        "wAlmSuppressed",
        "ePrioUnack",
        "eCmdResult",
        "uiCmdSeq",
        "eDevType",
    ),
    "ST_DeviceCmd": ("xSetAuto", "xSetManual", "xSetOos", "xReset", "xAck", "wAckReq", "wShelveReq", "wUnshelveReq"),
    "ST_PidSts": (
        "stCommon",
        "rSpTarget_eu",
        "rSp_eu",
        "rPv_eu",
        "rErr_pct",
        "rOut_pct",
        "rP_pct",
        "rI_pct",
        "rD_pct",
        "rDt_ms",
    ),
    "ST_PidCmd": ("rSp_eu", "rManualOut_pct", "stCommon"),
}

# Подписи тегов станции (то, чего нет в комментариях объявлений или что там сказано для разработчика)
STATION_TEXT = {
    "eMode": "режим станции: 1 Auto, 2 Manual",
    "eMethod": "способ регулирования: 1 ступенчатое, 2 ПИД уровня",
    "eControlAct": (
        "действующее управление: 0 ручное, 1 ступенчатое, 2 ПИД уровня, 3 по поплавкам, 4 аварийный уровень, "
        "5 сухой ход, 6 нет напряжения, 7 перезапуск"
    ),
    "eNe107": "статус NE 107 станции: 0 Good, 1 M, 2 S, 3 C, 4 F",
    "wState": "слово состояния (биты STN_ST_* флагмана)",
    "wCfgErr": "ошибки уставок (биты STN_CFG_* флагмана)",
    "uiPumpsRequired": "требуется насосов",
    "uiPumpsRunning": "насосов в работе",
    "uiPumpsAvailable": "насосов доступно в автомате",
    "uiLeadPump": "ведущий насос: 1–3, 0 — нет",
    "uiSeqRemain_s": "до следующего шага последовательного пуска",
    "eCmdResult": "результат последней команды станции (E_CmdResult)",
    "uiCmdSeq": "счётчик обработанных команд станции",
    "wAlmActive": "тревоги станции: бит slot − 1 активен",
    "wAlmUnack": "тревоги станции: бит slot − 1 не квитирован",
    "wAlmShelved": "тревоги станции: бит slot − 1 отложен, подавлен или выведен из работы",
    "ePrioUnack": "высший приоритет неквитированных тревог всех источников",
    "eLogExport": "состояние выгрузки журнала в CSV",
    "rLevel_m": "уровень, по которому работает станция",
    "rLevelSp_m": "действующее задание уровня",
    "rSpeedSp_pct": "общее задание частоты насосам",
    "udiEventSeq": "номер последней записи журнала",
    "udiLogOverwritten": "затёрто записей журнала",
}
STATION_CMD_TEXT = {
    "xSetAuto": "команда: станция в «Автомат»",
    "xSetManual": "команда: станция в «Ручной»",
    "xSetStepped": "команда: способ «ступенчатое»",
    "xSetLevelPid": "команда: способ «ПИД уровня»",
    "xAckAll": "команда: квитировать все тревоги станции, LIC101 и устройств",
    "xResetAll": "команда: общий сброс (как кнопка HS501)",
    "xSilence": "команда: выключить сирену (как кнопка HS502)",
    "xExportLog": "команда: выгрузить журнал в CSV",
    "xRevertCfg": "команда: откатить записанные уставки к действующей копии",
    "wAckReq": "маска: квитировать тревоги станции, бит slot − 1",
    "wShelveReq": "маска: отложить тревоги станции",
    "wUnshelveReq": "маска: вернуть отложенные тревоги станции",
    "udiAckId": "квитировать тревогу по номеру, 0 — нет",
    "udiShelveId": "отложить тревогу любого источника по номеру, 0 — нет",
    "udiUnshelveId": "вернуть отложенную тревогу по номеру, 0 — нет",
}
PID_TEXT = {
    "rSpTarget_eu": "задание после пределов, до рампы",
    "rSp_eu": "действующее задание уровня",
    "rPv_eu": "регулируемая величина (уровень)",
    "rErr_pct": "ошибка, % диапазона",
    "rOut_pct": "выход регулятора (задание частоты)",
    "rP_pct": "пропорциональная составляющая",
    "rI_pct": "интегральная составляющая",
    "rD_pct": "дифференциальная составляющая",
    "rDt_ms": "последний шаг расчёта",
    "eMode": "режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService",
    "eNe107": "статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F",
    "wStatus": "слово состояния",
    "wFault": "отказы",
    "wWarning": "предупреждения",
    "wCfgErr": "ошибки конфигурации",
    "wAlmActive": "бит i: тревога слота i активна",
    "wAlmUnack": "бит i: тревога слота i не квитирована",
    "wAlmShelved": "бит i: слот отложен оператором (Shelved)",
    "wAlmSuppressed": "бит i: слот подавлен логикой (SuppressedByDesign)",
    "ePrioUnack": "высший приоритет неквитированных тревог",
    "eCmdResult": "результат последней команды",
    "uiCmdSeq": "счётчик обработанных команд",
    "eDevType": "тип устройства",
}
PID_CMD_TEXT = {
    "rSp_eu": "задание оператора (при внешнем задании станции не действует)",
    "rManualOut_pct": "выход в Manual",
    "xSetAuto": "команда: в Auto",
    "xSetManual": "команда: в Manual",
    "xSetOos": "команда: вывести из работы",
    "xReset": "команда: сброс отказов и квитирование",
    "xAck": "команда: квитировать тревоги",
    "wAckReq": "маска: квитировать слоты",
    "wShelveReq": "маска: отложить слоты",
    "wUnshelveReq": "маска: вернуть слоты",
}

DECL_RE = re.compile(
    r"^\s*([A-Za-z_]\w*)\s*:(?!=)\s*"
    r"(ARRAY\s*\[[^\]]*\]\s*OF\s+[A-Za-z_][\w.]*|[A-Za-z_][\w.]*(?:\s*\(\s*[\w.]+\s*\))?)"
    r"\s*(?::=[^;]*)?;?\s*(?://\s*(.*))?$"
)


class SnapshotError(RuntimeError):
    """Флагман не прочитан или его объявления не разобраны."""


@dataclass(frozen=True)
class Commit:
    sha: str
    date: str
    subject: str


# --- чтение флагмана -----------------------------------------------------------------------------
def git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args], check=True, capture_output=True, encoding="utf-8", errors="strict"
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise SnapshotError(f"git {' '.join(args)}: {detail.strip()}") from exc
    return out.stdout


def show(repo: Path, rev: str, path: str) -> str:
    """Файл флагмана из коммита: переводы строк — LF, без BOM."""
    return git(repo, "show", f"{rev}:{path}").replace("\r\n", "\n").removeprefix("﻿")


def list_files(repo: Path, rev: str, prefix: str, suffix: str) -> list[str]:
    names = git(repo, "ls-tree", "-r", "--name-only", rev, "--", prefix).splitlines()
    return sorted(n for n in names if n.endswith(suffix))


def commit_info(repo: Path, rev: str) -> Commit:
    sha, date, subject = git(repo, "log", "-1", "--format=%H%n%cs%n%s", rev).splitlines()[:3]
    return Commit(sha, date, subject)


# --- разбор объявлений ST ------------------------------------------------------------------------
def strip_comments(line: str) -> tuple[str, str]:
    """Строка без комментария ``//`` (вне строковых литералов) и сам комментарий."""
    in_str = False
    for i, ch in enumerate(line):
        if ch == "'":
            in_str = not in_str
        elif not in_str and line.startswith("//", i):
            return line[:i], line[i + 2 :].strip()
    return line, ""


def parse_decls(lines: Iterable[str]) -> list[tuple[str, str, str]]:
    """Объявления ``имя : ТИП [:= …]; // комментарий`` по строкам (продолжения инициализаторов — нет)."""
    out: list[tuple[str, str, str]] = []
    for raw in lines:
        code, comment = strip_comments(raw)
        match = DECL_RE.match(code)
        if match:
            out.append((match.group(1), re.sub(r"\s+", " ", match.group(2)).strip(), comment))
    return out


def parse_gvl(text: str) -> dict[str, str]:
    """Переменные блоков ``VAR_GLOBAL`` и ``VAR_GLOBAL PERSISTENT RETAIN`` (константы не выгружаются)."""
    out: dict[str, str] = {}
    block: list[str] | None = None
    for line in text.splitlines():
        head = strip_comments(line)[0].strip()
        if head.startswith("VAR_GLOBAL"):
            block = None if "CONSTANT" in head.split() else []
            continue
        if head.startswith("END_VAR"):
            if block is not None:
                out.update((name, typ) for name, typ, _ in parse_decls(block))
            block = None
            continue
        if block is not None:
            block.append(line)
    return out


def parse_dut(text: str) -> tuple[str, dict[str, Any]]:
    """``TYPE <имя> : STRUCT … END_STRUCT`` или перечисление ``( … ) <БАЗА>;``."""
    match = re.search(r"^\s*TYPE\s+(\w+)\s*:", text, re.M)
    if not match:
        raise SnapshotError("нет TYPE")
    name = match.group(1)
    body = text[match.end() :]
    if re.match(r"\s*STRUCT\b", body):
        inner = body.split("END_STRUCT", 1)[0].split("STRUCT", 1)[1]
        members = {n: {"type": t, "comment": c} for n, t, c in parse_decls(inner.splitlines())}
        return name, {"kind": "struct", "members": members}
    enum = re.match(r"\s*\((.*?)\)\s*(\w+)?\s*;", body, re.S)
    if not enum:
        raise SnapshotError(f"{name}: не структура и не перечисление")
    values: dict[str, int] = {}
    for item in enum.group(1).splitlines():
        code = strip_comments(item)[0]
        for part in code.split(","):
            m = re.match(r"\s*(\w+)\s*:=\s*(-?\d+)\s*$", part)
            if m:
                values[m.group(1)] = int(m.group(2))
    return name, {"kind": "enum", "base": (enum.group(2) or "INT").upper(), "values": values}


def pl_types(contract: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Типы plc-process-lib из контракта флагмана: структуры, ФБ (входы, выходы, VAR_IN_OUT), перечисления."""
    types: Mapping[str, Any] = contract["types"]
    out: dict[str, dict[str, Any]] = {}

    def fb_members(name: str) -> dict[str, dict[str, str]]:
        info = types[name]
        base = info.get("base")
        members = fb_members(base) if base else {}
        for member, (typ, _init, role) in info["members"].items():
            if role in ("input", "output", "inout"):
                members[member] = {"type": qualify(typ, types), "role": role}
        return members

    for name, info in types.items():
        kind = info["kind"]
        key = f"PL.{name}"
        if kind == "enum":
            # Перечисления библиотеки — strict на INT (контракт plc-process-lib, раздел 2.7)
            out[key] = {"kind": "enum", "base": "INT", "values": dict(info["values"])}
        elif kind == "struct":
            members = {m: {"type": qualify(t, types)} for m, (t, _init, _role) in info["members"].items()}
            order = PL_ORDER.get(name)
            if order:
                members = {m: members[m] for m in order} | members
            out[key] = {"kind": "struct", "members": members}
        elif kind == "fb":
            out[key] = {"kind": "fb", "members": fb_members(name)}
    return out


def qualify(typ: str, pl: Mapping[str, Any]) -> str:
    """Тип члена библиотеки — с пространством имён ``PL.``, если это тип библиотеки."""
    base = typ.strip()
    return f"PL.{base}" if base in pl else base


# --- снимок ------------------------------------------------------------------------------------
@dataclass
class Sources:
    commit: Commit
    rev: str
    texts: dict[str, str]


def read_flagship(repo: Path, rev: str) -> Sources:
    commit = commit_info(repo, rev)
    paths = [SCADA_TAGS, SCADA_ALARMS, ALARM_LIST, SYMBOL_RULES, PL_CONTRACT]
    paths += list_files(repo, commit.sha, GVL_DIR, ".st")
    paths += list_files(repo, commit.sha, DUT_DIR, ".dut.st")
    return Sources(commit, rev, {p: show(repo, commit.sha, p) for p in paths})


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_symbols(src: Sources) -> dict[str, Any]:
    rules: dict[str, Any] = json.loads(src.texts[SYMBOL_RULES])
    exported = {r["gvl"] for r in rules["rules"]}
    gvls: dict[str, dict[str, str]] = {}
    for path, text in src.texts.items():
        if path.startswith(GVL_DIR + "/"):
            name = Path(path).name.split(".", 1)[0]
            if name in exported:
                gvls[name] = parse_gvl(text)
    missing = sorted(exported - set(gvls))
    if missing:
        raise SnapshotError(f"нет объявлений глобальных списков из правил символов: {', '.join(missing)}")
    types: dict[str, dict[str, Any]] = {}
    for path, text in src.texts.items():
        if path.startswith(DUT_DIR + "/"):
            name, info = parse_dut(text)
            types[name] = info
    contract: dict[str, Any] = json.loads(src.texts[PL_CONTRACT])
    types.update(pl_types(contract))
    files = {p: sha256(t) for p, t in sorted(src.texts.items()) if not p.startswith((GVL_DIR + "/", DUT_DIR + "/"))}
    files["src/GVLs/**"] = sha256("".join(src.texts[p] for p in sorted(src.texts) if p.startswith(GVL_DIR + "/")))
    files["src/DUTs/**"] = sha256("".join(src.texts[p] for p in sorted(src.texts) if p.startswith(DUT_DIR + "/")))
    return {
        "_doc": [
            f"AUTO-GENERATED by {TOOL} — не редактировать.",
            "Интерфейс флагмана КНС-1 для проверки путей OPC UA и ST: объявления глобальных списков из правил "
            "символьной конфигурации, типы флагмана и plc-process-lib, правила доступа. Читает "
            "tools_project/flagship_symbols.py.",
        ],
        "flagship": {
            "repository": "kns-pump-station",
            "rev": src.rev,
            "commit": src.commit.sha,
            "date": src.commit.date,
            "subject": src.commit.subject,
            "plc_process_lib": contract.get("source", ""),
            "files": files,
        },
        "node_prefix": NODE_PREFIX,
        "symbol_rules": {k: v for k, v in rules.items() if k != "_doc"},
        "gvls": gvls,
        "types": dict(sorted(types.items())),
        # константы plc-process-lib (PL.GVL_Const): тип и значение — для проверки сгенерированного ST
        "pl_constants": {k: {"type": v[0], "value": v[1]} for k, v in sorted(contract["gvls"]["GVL_Const"].items())},
    }


def tag_name(member: str) -> str:
    """Имя тега по имени поля, как у iolistgen: без префикса типа и единицы (``uiSeqRemain_s`` → ``SeqRemain``)."""
    match = re.match(r"^[a-z]+([A-Z]\w*)$", member)
    if not match:
        raise SnapshotError(f"поле {member}: нет префикса типа")
    return re.sub(r"_[A-Za-z0-9]+$", "", match.group(1))


def unit_of(member: str, eu: str = "") -> str:
    match = re.search(r"_([A-Za-z0-9]+)$", member)
    if not match:
        return ""
    suffix = match.group(1)
    return eu if suffix == "eu" else UNITS.get(suffix, "")


def iec_type(typ: str, types: Mapping[str, Mapping[str, Any]]) -> str:
    """Тип узла OPC UA: перечисление — его база (INT), элементарный — как есть."""
    base = typ.split("(")[0].strip()
    if base in ELEMENTARY:
        return base
    info = types.get(base)
    if info and info["kind"] == "enum":
        return str(info["base"])
    raise SnapshotError(f"тип {typ}: не элементарный и не перечисление")


@dataclass(frozen=True)
class TagRow:
    tag: str
    description: str
    device: str
    device_type: str
    hmi_group: str
    data_type: str
    access: str
    units: str
    plc_path: str

    def cells(self) -> list[str]:
        values = {
            "tag": self.tag,
            "description": self.description,
            "device": self.device,
            "device_type": self.device_type,
            "hmi_group": self.hmi_group,
            "data_type": self.data_type,
            "access": self.access,
            "units": self.units,
            "plc_path": self.plc_path,
            "opcua_node_id": NODE_PREFIX + self.plc_path,
        }
        return [values.get(col, "") for col in TAG_COLUMNS]


def struct_rows(
    symbols: Mapping[str, Any],
    *,
    type_name: str,
    path: str,
    device: str,
    title: str,
    device_type: str,
    group: str,
    access: str,
    texts: Mapping[str, str],
    tag_prefix: str,
    eu: str = "",
) -> list[TagRow]:
    """Теги полей структуры: вложенный ``stCommon`` разворачивается, массивы и резерв пропускаются."""
    types: Mapping[str, Mapping[str, Any]] = symbols["types"]
    info = types[type_name]
    rows: list[TagRow] = []
    for member, decl in info["members"].items():
        typ = str(decl["type"])
        if typ.startswith("ARRAY") or member.startswith("wReserve"):
            continue
        if member == "stCommon":
            rows += struct_rows(
                symbols,
                type_name=typ,
                path=f"{path}.stCommon",
                device=device,
                title=title,
                device_type=device_type,
                group=group,
                access=access,
                texts=texts,
                tag_prefix=tag_prefix,
            )
            continue
        text = texts.get(member) or str(decl.get("comment", "")) or member
        rows.append(
            TagRow(
                tag=f"{tag_prefix}{tag_name(member)}",
                description=f"{title}: {text}",
                device=device,
                device_type=device_type,
                hmi_group=group,
                data_type=iec_type(typ, types),
                access=access,
                units=unit_of(member, eu),
                plc_path=f"{path}.{member}",
            )
        )
    return rows


def station_tag_rows(symbols: Mapping[str, Any]) -> list[TagRow]:
    station = symbols["gvls"]["GVL_Station"]
    app = APP + "GVL_Station"
    sts_type, cmd_type = station["stStationSts"], station["stStationCmd"]
    pid_type = symbols["types"][station["fbLIC101"]]["members"]["stSts"]["type"]
    pid_cmd_type = station["stLIC101Cmd"]
    common = {"device_type": "Station", "group": "Станция"}
    return [
        *struct_rows(
            symbols,
            type_name=sts_type,
            path=f"{app}.stStationSts",
            device="KNS1",
            title="Станция КНС-1",
            access="R",
            texts=STATION_TEXT,
            tag_prefix="KNS1.",
            **common,
        ),
        *struct_rows(
            symbols,
            type_name=cmd_type,
            path=f"{app}.stStationCmd",
            device="KNS1",
            title="Станция КНС-1",
            access="RW",
            texts=STATION_CMD_TEXT,
            tag_prefix="KNS1.Cmd.",
            **common,
        ),
        *struct_rows(
            symbols,
            type_name=pid_type,
            path=f"{app}.fbLIC101.stSts",
            device="LIC101",
            title="Регулятор уровня LIC101",
            device_type="Pid",
            group="Станция",
            access="R",
            texts=PID_TEXT,
            tag_prefix="LIC101.",
            eu="м",
        ),
        *struct_rows(
            symbols,
            type_name=pid_cmd_type,
            path=f"{app}.stLIC101Cmd",
            device="LIC101",
            title="Регулятор уровня LIC101",
            device_type="Pid",
            group="Станция",
            access="RW",
            texts=PID_CMD_TEXT,
            tag_prefix="LIC101.Cmd.",
            eu="м",
        ),
    ]


def csv_text(header: Sequence[str], comments: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    buf = io.StringIO()
    for line in comments:
        buf.write(f"# {line}\n")
    writer = csv.writer(buf, delimiter=";", lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue()


def source_note(src: Sources) -> str:
    """Источник в заголовке CSV: коммит флагмана записан в flagship_symbols.json (не в каждом файле)."""
    return "источник: kns-pump-station, коммит — flagship_symbols.json"


def interface_part(text: str) -> str:
    """Снимок без сведений о коммите: для --check коммит флагмана без изменений интерфейса — не расхождение."""
    data = json.loads(text)
    data["flagship"] = {k: v for k, v in data["flagship"].items() if k not in ("rev", "commit", "date", "subject")}
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def is_stale(path: Path, text: str) -> bool:
    if not path.exists():
        return True
    old = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return interface_part(old) != interface_part(text)
    return old != text


def station_tags_text(src: Sources, symbols: Mapping[str, Any]) -> str:
    rows = station_tag_rows(symbols)
    comments = [
        f"AUTO-GENERATED by {TOOL} — не редактировать; {source_note(src)}",
        "Теги станции (KNS1) и регулятора уровня (LIC101) флагмана в формате scada_tags.csv iolistgen:",
        "состояние — GVL_Station.stStationSts и fbLIC101.stSts (R), команды — stStationCmd и stLIC101Cmd (RW);",
        "типы — docs/DESIGN.md 3.1 флагмана и контракт plc-process-lib,",
        "права — tools_project/codesys/symbol_rules.json флагмана",
    ]
    return csv_text(TAG_COLUMNS, comments, (r.cells() for r in rows))


def station_alarms_text(src: Sources) -> str:
    raw = src.texts[ALARM_LIST]
    lines = [ln for ln in raw.splitlines() if ln and not ln.startswith("#")]
    rows: list[list[str]] = []
    skipped: list[str] = []
    for row in csv.DictReader(io.StringIO("\n".join(lines)), delimiter=";"):
        if row["source"] != "station":
            continue
        if row["priority"] == "None":
            skipped.append(row["code"])
            continue
        device = row["tag"]
        slot = int(row["slot"])
        bit = slot - 1 if device == "KNS1" else slot
        rows.append(
            [
                row["id"],
                row["code"],
                device,
                str(slot),
                row["priority"],
                row["text_ru"],
                f"{device}.AlmActive",
                f"{device}.AlmUnack",
                f"{device}.Cmd.AckReq",
                str(bit),
                "",
                row["delay_s"] or "0",
            ]
        )
    comments = [
        f"AUTO-GENERATED by {TOOL} — не редактировать; {source_note(src)}",
        "Тревоги станции флагмана (docs/05_alarm_list.csv, source = station) в формате scada_alarms.csv:",
        "id = 100000 + slot, бит в словах тревог станции (stStationSts.wAlmActive, wAlmUnack, wAlmShelved) = slot - 1;",
        f"выключенные (priority None) не входят: {', '.join(skipped) or 'нет'}",
    ]
    return csv_text(ALARM_COLUMNS, comments, rows)


def generate(src: Sources) -> dict[Path, str]:
    symbols = build_symbols(src)
    return {
        OUT_DIR / "scada_tags.csv": src.texts[SCADA_TAGS],
        OUT_DIR / "scada_alarms.csv": src.texts[SCADA_ALARMS],
        OUT_DIR / "station_tags.csv": station_tags_text(src, symbols),
        OUT_DIR / "station_alarms.csv": station_alarms_text(src),
        OUT_DIR / "flagship_symbols.json": json.dumps(symbols, ensure_ascii=False, indent=1) + "\n",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(os.environ.get("KNS_REPO", str(DEFAULT_FLAGSHIP))),
        help="репозиторий флагмана (по умолчанию ../kns-pump-station или KNS_REPO)",
    )
    parser.add_argument("--rev", default="main", help="коммит или ветка флагмана (по умолчанию main)")
    parser.add_argument("--check", action="store_true", help="только сверить schema/source с флагманом")
    args = parser.parse_args(argv)
    try:
        src = read_flagship(args.repo, args.rev)
        files = generate(src)
    except SnapshotError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 2
    note = f"флагман {src.commit.sha[:7]} ({src.commit.date}, {src.commit.subject})"
    if args.check:
        stale = [p for p, text in files.items() if is_stale(p, text)]
        for p in stale:
            print(f"устарел: {p.relative_to(REPO).as_posix()}")
        print(f"{note}: {'есть расхождения' if stale else 'снимок актуален'}")
        return 1 if stale else 0
    stale = [p for p, text in files.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
    for p in stale:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(files[p], encoding="utf-8", newline="\n")
        print(f"записан: {p.relative_to(REPO).as_posix()}")
    print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
