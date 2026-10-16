"""Шлюз команд MQTT: проверки до устройства и ответ cmd_ack.

Правила — как у шлюза команд ПЛК (docs/data_schema.md, command.schema.json,
command_whitelist.csv):

- топик ``<site>/<area>/<unit>/<device>/cmd/<command>`` нашей станции, иначе сообщение
  отбрасывается без ответа (некуда отвечать);
- JSON-объект с читаемым ``cmd_id`` — иначе без ответа (ответ адресуется по cmd_id), счётчик
  ``PLC1/cmd_rejected`` растёт;
дальше — по порядку docs/data_schema.md, раздел 5.1, до первой ошибки:

1. ``retained`` — отказ: команда, сохранённая брокером, выполнилась бы при каждом подключении;
2. состав и типы полей по command.schema.json — ``invalid_payload`` (диапазон значения
   проверяется отдельно, в п. 6, чтобы ответ был ``out_of_range``);
3. мажорная версия ``schema_version`` = 1 — иначе ``unsupported_version``;
4. команда в теле совпадает с последним уровнем топика — иначе ``topic_mismatch``;
5. пара (устройство, команда) в белом списке — иначе ``not_whitelisted``;
6. значение в [min; max] белого списка — иначе ``out_of_range``;
7. возраст ``ts`` не больше допуска (30 с) — иначе ``expired``;
8. ``cmd_id`` не встречался среди последних 16 команд — иначе ``duplicate``;
9. не больше 10 команд за 10 с на узел — иначе ``rate_limited``;
10. команда пишется в ``GVL_Hmi.st<DEV>Cmd``; результат устройства (``uiCmdSeq`` +1,
    ``eCmdResult``) превращается в ``ok`` или ``device_rejected``, нет ответа — ``timeout``.
    Команды-значения (``SpeedSp``) ФБ не квитирует: ``ok`` — после записи.
"""

from __future__ import annotations

import json
import math
import re
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Any

from .schema import (
    COMMANDS,
    MASK_COMMANDS,
    SCHEMA_MAJOR,
    VALUE_COMMANDS,
    Topics,
    WhitelistEntry,
    command_whitelist,
)

CMD_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,36}$")
VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
ORIGIN_RE = re.compile(r"^[ -~]{1,64}$")
TS_MIN = 1577836800000
TS_MAX = 4102444800000
ALLOWED_FIELDS = frozenset({"schema_version", "cmd_id", "ts", "origin", "command", "value"})


@dataclass
class Decision:
    """Решение шлюза по одному сообщению."""

    device: str
    command: str  # последний уровень топика, как получен
    cmd_id: str | None  # None — ответить нельзя
    reason: str  # ok — передать устройству; иначе причина отказа
    value: float | None = None
    entry: WhitelistEntry | None = None
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.reason == "ok"


@dataclass
class GatewayStats:
    accepted: int = 0
    rejected: int = 0
    dropped: int = 0  # без ответа: чужой топик, нечитаемый cmd_id
    by_reason: dict[str, int] = field(default_factory=dict)


def _is_number(v: object) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(float(v))


class CommandGateway:
    def __init__(
        self,
        topics: Topics,
        *,
        whitelist: dict[tuple[str, str], WhitelistEntry] | None = None,
        max_age_s: float = 30.0,
        rate_limit: int = 10,
        rate_window_s: float = 10.0,
        dup_memory: int = 16,
    ) -> None:
        self.topics = topics
        self.whitelist = whitelist if whitelist is not None else command_whitelist()
        self.max_age_ms = int(max_age_s * 1000)
        self.rate_limit = rate_limit
        self.rate_window_ms = int(rate_window_s * 1000)
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._dup_memory = dup_memory
        self._rate: deque[int] = deque()  # моменты принятых команд (лимит на узел, не на устройство)
        self.stats = GatewayStats()

    def _remember(self, cmd_id: str) -> None:
        self._seen[cmd_id] = None
        while len(self._seen) > self._dup_memory:
            self._seen.popitem(last=False)

    def _count(self, d: Decision) -> Decision:
        if d.cmd_id is None:
            self.stats.dropped += 1
        elif d.passed:
            self.stats.accepted += 1  # прошла шлюз; итог устройства учитывает note_device_result
        else:
            self.stats.rejected += 1
            self.stats.by_reason[d.reason] = self.stats.by_reason.get(d.reason, 0) + 1
        return d

    def note_device_result(self, accepted: bool, reason: str) -> None:
        """Команда прошла шлюз, но устройство отказало или не ответило: перенос в rejected."""
        if not accepted:
            self.stats.accepted -= 1
            self.stats.rejected += 1
            self.stats.by_reason[reason] = self.stats.by_reason.get(reason, 0) + 1

    def check(self, topic: str, payload: bytes, *, retained: bool, now_ms: int) -> Decision:
        parsed = self.topics.parse_command_topic(topic)
        if parsed is None:
            return self._count(Decision("", "", None, "topic_mismatch", detail="чужой топик"))
        device, command = parsed
        try:
            body = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._count(Decision(device, command, None, "invalid_payload", detail="не JSON"))
        if not isinstance(body, dict):
            return self._count(Decision(device, command, None, "invalid_payload", detail="не объект"))
        cmd_id = body.get("cmd_id")
        if not isinstance(cmd_id, str) or not CMD_ID_RE.match(cmd_id):
            return self._count(Decision(device, command, None, "invalid_payload", detail="нет cmd_id"))
        d = self._check_body(device, command, cmd_id, body, retained, now_ms)
        if d.reason != "duplicate":
            self._remember(cmd_id)
        return self._count(d)

    def _check_body(
        self, device: str, command: str, cmd_id: str, body: dict[str, Any], retained: bool, now_ms: int
    ) -> Decision:
        def reject(reason: str, detail: str = "") -> Decision:
            return Decision(device, command, cmd_id, reason, detail=detail)

        if retained:
            return reject("retained")
        # 2. состав и типы полей (command.schema.json); диапазон значения — отдельная проверка 6
        version = body.get("schema_version")
        if not isinstance(version, str) or not VERSION_RE.match(version):
            return reject("invalid_payload", "schema_version")
        extra = set(body) - ALLOWED_FIELDS
        if extra:
            return reject("invalid_payload", f"лишние поля: {sorted(extra)}")
        ts = body.get("ts")
        if not isinstance(ts, int) or isinstance(ts, bool) or not TS_MIN <= ts <= TS_MAX:
            return reject("invalid_payload", "ts")
        origin = body.get("origin")
        if not isinstance(origin, str) or not ORIGIN_RE.match(origin):
            return reject("invalid_payload", "origin")
        body_cmd = body.get("command")
        if not isinstance(body_cmd, str) or body_cmd not in COMMANDS:
            return reject("invalid_payload", "command")
        has_value = "value" in body
        value = body.get("value")
        if has_value and not _is_number(value):
            return reject("invalid_payload", "value не число")
        needs_value = body_cmd in VALUE_COMMANDS or body_cmd in MASK_COMMANDS
        if needs_value and not has_value:
            return reject("invalid_payload", "нет value")
        if not needs_value and has_value:
            return reject("invalid_payload", "value у импульсной команды")
        if body_cmd in MASK_COMMANDS and not (isinstance(value, int) and 0 <= value <= 0xFFFF):
            return reject("invalid_payload", "маска 0…65535")
        # 3. мажорная версия схемы
        if int(version.split(".")[0]) != SCHEMA_MAJOR:
            return reject("unsupported_version", version)
        # 4. команда в теле и в топике
        if body_cmd != command:
            return reject("topic_mismatch", f"в топике {command}, в теле {body_cmd}")
        entry = self.whitelist.get((device, command))
        if entry is None:
            return reject("not_whitelisted")
        fvalue: float | None = None
        if has_value:
            fvalue = float(value)  # type: ignore[arg-type]
            lo = entry.min if entry.min is not None else -math.inf
            hi = entry.max if entry.max is not None else math.inf
            if command == "SpeedSp":  # схема: 0…100 % независимо от списка
                lo, hi = max(lo, 0.0), min(hi, 100.0)
            if not lo <= fvalue <= hi:
                return reject("out_of_range", f"{fvalue} вне [{lo}; {hi}]")
        if abs(now_ms - ts) > self.max_age_ms:
            return reject("expired", f"возраст {(now_ms - ts) / 1000:.1f} с")
        if cmd_id in self._seen:
            return reject("duplicate")
        window = self._rate
        while window and now_ms - window[0] > self.rate_window_ms:
            window.popleft()
        if len(window) >= self.rate_limit:
            return reject("rate_limited")
        window.append(now_ms)
        return Decision(device, command, cmd_id, "ok", value=fvalue, entry=entry)
