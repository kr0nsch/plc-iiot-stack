"""Источник OPC UA: опрос сервера ПЛК или эмулятора в течение N минут (истории нет).

Узлы строятся по scada_tags.csv: `ns=4;s=|var|CODESYS Control Win V3.Application.GVL_...`
(шаблон, номер пространства имён и имя устройства — в [opcua] настроек). Если задан URI
пространства имён, номер берётся с сервера.

Безопасность (docs/security.md): логин — из настроек, пароль — только из переменной окружения;
политика Basic256Sha256 / Aes128 задаётся строкой безопасности asyncua
"Basic256Sha256,SignAndEncrypt,<cert клиента>,<ключ клиента>[,<cert сервера>]".
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TextIO

from kns_report.config import OpcUaConfig
from kns_report.samples import SeriesSet, Value, write_jsonl_record
from kns_report.tagmodel import TagInfo

log = logging.getLogger(__name__)

MAX_CONSECUTIVE_FAILURES = 10


class UaClient(Protocol):
    """Часть интерфейса asyncua.Client, которой пользуется опрос (подменяется в тестах)."""

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    def set_user(self, username: str) -> None: ...
    def set_password(self, pwd: str) -> None: ...
    async def set_security_string(self, string: str) -> None: ...
    async def get_namespace_index(self, uri: str) -> int: ...
    def get_node(self, nodeid: Any) -> Any: ...
    async def read_values(self, nodes: Any) -> list[Any]: ...


def node_id(cfg: OpcUaConfig, info: TagInfo, ns_index: int) -> str:
    """NodeId тега: шаблон из настроек с ns, именем устройства и путём в ПЛК."""
    return cfg.node_id_template.format(ns=ns_index, device=cfg.device_name, path=info.plc_path)


def _default_client(endpoint: str, timeout: float) -> UaClient:
    from asyncua.client.client import Client

    client: UaClient = Client(url=endpoint, timeout=timeout)
    return client


def _as_value(raw: Any) -> Value | None:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int | float):
        number = float(raw)
        return raw if math.isfinite(number) else None
    return None


async def sample(
    cfg: OpcUaConfig,
    tags: list[TagInfo],
    *,
    minutes: float,
    interval_s: float,
    password: str | None = None,
    client_factory: Callable[[str, float], UaClient] = _default_client,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    save_to: TextIO | None = None,
) -> SeriesSet:
    """Опрашивать теги каждые interval_s секунд в течение minutes минут."""
    if interval_s <= 0 or minutes <= 0:
        raise ValueError("интервал опроса и длительность должны быть больше нуля")
    client = client_factory(cfg.endpoint, max(4.0, interval_s * 4))
    if cfg.user:
        client.set_user(cfg.user)
        if password:
            client.set_password(password)
    if cfg.security:
        await client.set_security_string(cfg.security)
    result = SeriesSet()
    await client.connect()
    try:
        ns_index = await client.get_namespace_index(cfg.namespace_uri) if cfg.namespace_uri else cfg.ns_index
        nodes = [client.get_node(node_id(cfg, info, ns_index)) for info in tags]
        polls = max(1, round(minutes * 60.0 / interval_s)) + 1
        t0 = monotonic()
        failures = 0
        for index in range(polls):
            ts = clock()
            try:
                raw_values = await client.read_values(nodes)
                failures = 0
            except Exception as exc:  # сбой связи: пропуск опроса, после серии сбоев — стоп
                failures += 1
                log.warning("опрос %d: ошибка чтения: %s", index, exc)
                if failures >= MAX_CONSECUTIVE_FAILURES:
                    log.error("%d сбоев подряд — опрос остановлен, отчёт по собранным данным", failures)
                    break
            else:
                values: dict[str, Value | None] = {}
                for info, raw in zip(tags, raw_values, strict=True):
                    value = _as_value(raw)
                    values[info.tag] = value
                    if value is not None:
                        result.add(info.tag, ts, value)
                if save_to is not None:
                    write_jsonl_record(save_to, ts, values)
            if index + 1 < polls:
                delay = t0 + (index + 1) * interval_s - monotonic()
                if delay > 0:
                    await sleep(delay)
    finally:
        await client.disconnect()
    return result.sort()


def sample_to_file(
    cfg: OpcUaConfig,
    tags: list[TagInfo],
    *,
    minutes: float,
    interval_s: float,
    password: str | None,
    save_path: Path | None,
) -> SeriesSet:
    """Синхронная обёртка для командной строки."""

    async def run() -> SeriesSet:
        if save_path is None:
            return await sample(cfg, tags, minutes=minutes, interval_s=interval_s, password=password)
        with save_path.open("w", encoding="utf-8", newline="\n") as handle:
            return await sample(cfg, tags, minutes=minutes, interval_s=interval_s, password=password, save_to=handle)

    return asyncio.run(run())
