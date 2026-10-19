"""Символы флагмана КНС-1: тип и доступ OPC UA любого пути ``Application.<GVL>.<…>``.

Назначение: проверить, что узлы Telegraf, теги эмулятора, пути каталога, белого списка и
сгенерированного ST ссылаются на настоящие переменные флагмана с подходящим типом и правами. Данные —
``schema/source/flagship_symbols.json`` (снимок ``flagship_snapshot.py``: объявления глобальных
списков, типы флагмана и plc-process-lib, правила символьной конфигурации флагмана).

Правила доступа — как у ``tools_project/codesys/symbol_config.py`` флагмана: первое подходящее правило
списка (шаблоны имён fnmatch без учёта регистра) задаёт доступ переменной для сборки ``sim`` или
``site``; правило типа ограничивает поле структуры, но не выше прав переменной. Переменная без правила
не выгружается. Члены ФБ видны только входы и выходы (VAR_IN_OUT — ссылки, значения в символах нет).

Автор: kr0nsch. Документ: docs/ARCHITECTURE.md, раздел «Привязка к флагману».
"""

from __future__ import annotations

import fnmatch
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
SYMBOLS_FILE = REPO / "schema" / "source" / "flagship_symbols.json"
APP = "Application."
BUILDS = ("sim", "site")
ACCESS_RANK = {"": 0, "Read": 1, "ReadWrite": 2}

ELEMENTARY = frozenset(
    {"BOOL", "BYTE", "WORD", "DWORD", "LWORD", "SINT", "USINT", "INT", "UINT", "DINT", "UDINT", "LINT", "ULINT"}
    | {"REAL", "LREAL", "TIME", "LTIME", "DATE", "TOD", "DT"}
)
ARRAY_RE = re.compile(r"^ARRAY\s*\[\s*([^\].]+)\s*\.\.\s*([^\]]+)\]\s*OF\s+(.+)$")
STEP_RE = re.compile(r"^([A-Za-z_]\w*)(?:\[(\d+)\])?$")


class SymbolError(LookupError):
    """Путь не разрешается: нет переменной, поля, или переменная не выгружается в символы."""


@dataclass(frozen=True)
class Symbol:
    path: str  # Application.GVL_Station.stStationSts.eMode
    declared: str  # тип из объявления: E_StationMode, PL.E_Ne107Status, REAL
    iec_type: str  # тип узла OPC UA: перечисление — его база
    access: Mapping[str, str]  # сборка → Read | ReadWrite | "" (не выгружается)

    def readable(self, build: str) -> bool:
        return ACCESS_RANK[self.access.get(build, "")] >= ACCESS_RANK["Read"]

    def writable(self, build: str) -> bool:
        return self.access.get(build, "") == "ReadWrite"


class FlagshipSymbols:
    def __init__(self, data: Mapping[str, Any]) -> None:
        self.data = data
        self.gvls: Mapping[str, Mapping[str, str]] = data["gvls"]
        self.types: Mapping[str, Mapping[str, Any]] = data["types"]
        self.rules: Mapping[str, Any] = data["symbol_rules"]
        self.node_prefix: str = data["node_prefix"]

    @property
    def commit(self) -> str:
        return str(self.data["flagship"]["commit"])

    def var_access(self, gvl: str, var: str) -> dict[str, str]:
        """Доступ переменной списка по правилам символов (первое подходящее правило)."""
        for rule in self.rules["rules"]:
            if rule["gvl"] != gvl:
                continue
            if any(fnmatch.fnmatchcase(var.lower(), pat.lower()) for pat in rule["vars"]):
                spec = rule["access"]
                if isinstance(spec, str):
                    return dict.fromkeys(BUILDS, spec)
                return {b: str(spec.get(b, "")) for b in BUILDS}
        return dict.fromkeys(BUILDS, "")

    def member_rule(self, type_name: str, member: str) -> str | None:
        for rule in self.rules.get("types", []):
            if rule["type"] == type_name:
                for pat, access in rule["members"]:
                    if fnmatch.fnmatchcase(member.lower(), str(pat).lower()):
                        return str(access)
        return None

    def resolve(self, path: str) -> Symbol:
        """Тип и доступ пути ``Application.<GVL>.<переменная>[.<поле>…]`` (индексы массивов — ``[n]``)."""
        if not path.startswith(APP):
            raise SymbolError(f"{path}: путь должен начинаться с {APP}")
        parts = path[len(APP) :].split(".")
        if len(parts) < 2:
            raise SymbolError(f"{path}: нужен список и переменная")
        gvl = parts[0]
        if gvl not in self.gvls:
            raise SymbolError(f"{path}: список {gvl} не выгружается в символы флагмана")
        first = STEP_RE.match(parts[1])
        if not first or first.group(1) not in self.gvls[gvl]:
            raise SymbolError(f"{path}: нет переменной {parts[1]} в {gvl}")
        access = self.var_access(gvl, first.group(1))
        if not any(access.values()):
            raise SymbolError(f"{path}: переменная {gvl}.{first.group(1)} не выгружается (нет правила)")
        typ = self._index(self.gvls[gvl][first.group(1)], first.group(2), path)
        for step in parts[2:]:
            m = STEP_RE.match(step)
            if not m:
                raise SymbolError(f"{path}: шаг {step!r} не разобран")
            name = m.group(1)
            info = self.types.get(typ)
            if info is None or info["kind"] not in ("struct", "fb"):
                raise SymbolError(f"{path}: {typ} не структура и не ФБ, поля {name} нет")
            member = info["members"].get(name)
            if member is None or member.get("role") == "inout":
                raise SymbolError(f"{path}: у {typ} нет поля {name}, видимого в символах")
            rule = self.member_rule(typ, name)
            if rule is not None:
                access = {b: rule if ACCESS_RANK[rule] < ACCESS_RANK[a] else a for b, a in access.items()}
            typ = self._index(str(member["type"]), m.group(2), path)
        return Symbol(path, typ, self.iec_type(typ, path), access)

    def _index(self, typ: str, index: str | None, path: str) -> str:
        if index is None:
            return typ
        m = ARRAY_RE.match(typ)
        if not m:
            raise SymbolError(f"{path}: {typ} не массив")
        return m.group(3).strip()

    def iec_type(self, typ: str, path: str = "") -> str:
        base = typ.split("(")[0].strip()
        if base in ELEMENTARY or base in ("STRING", "WSTRING"):
            return base
        info = self.types.get(base)
        if info is not None and info["kind"] == "enum":
            return str(info["base"])
        return base  # структура, ФБ или массив: не лист

    def node_id(self, path: str) -> str:
        return f"{self.node_prefix}{path}"


@cache
def load(path: Path = SYMBOLS_FILE) -> FlagshipSymbols:
    return FlagshipSymbols(json.loads(path.read_text(encoding="utf-8")))


def st_paths(text: str) -> set[str]:
    """Пути переменных флагмана в тексте ST (без комментариев): ``GVL_<Имя>.<…>``, с префиксом ``Application.``."""
    code = re.sub(r"\(\*.*?\*\)", "", re.sub(r"//[^\n]*", "", text), flags=re.S)
    found = re.findall(r"\b(GVL_(?:Devices|Hmi|IO|Station|Log|Persist|Sim|Time)(?:\.\w+(?:\[\d+\])?)+)", code)
    return {APP + p for p in found}
