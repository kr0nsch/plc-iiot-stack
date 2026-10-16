"""Источник OPC UA с подменным клиентом: узлы, опрос по часам, сбои связи, запись выборки."""

from __future__ import annotations

import asyncio
import io
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from kns_report.aggregate import build_report
from kns_report.cli import required_tags
from kns_report.config import ReportConfig
from kns_report.opcua_source import MAX_CONSECUTIVE_FAILURES, UaClient, sample
from kns_report.samples import load_jsonl
from kns_report.tagmodel import AlarmDef, TagInfo
from kns_report.timeutil import ceil_hour, floor_hour

from .conftest import FIXTURES, GENERATED_AT, MSK


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.t = 0.0
        self.start = start

    def now(self) -> datetime:
        return self.start + timedelta(seconds=self.t)

    def mono(self) -> float:
        return self.t

    async def sleep(self, seconds: float) -> None:
        self.t += seconds


class FakeClient:
    """Отдаёт значения из записанной выборки по номеру опроса; может «ронять» чтения."""

    def __init__(self, frames: list[dict[str, Any]], fail_reads: set[int] | None = None) -> None:
        self.frames = frames
        self.fail_reads = fail_reads or set()
        self.reads = 0
        self.connected = False
        self.disconnected = False
        self.user: str | None = None
        self.password: str | None = None
        self.security: str | None = None
        self.node_ids: list[str] = []
        self.ns_uri: str | None = None
        self.tag_order: list[str] = []

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.disconnected = True

    def set_user(self, username: str) -> None:
        self.user = username

    def set_password(self, pwd: str) -> None:
        self.password = pwd

    async def set_security_string(self, string: str) -> None:
        self.security = string

    async def get_namespace_index(self, uri: str) -> int:
        self.ns_uri = uri
        return 7

    def get_node(self, nodeid: Any) -> Any:
        self.node_ids.append(str(nodeid))
        return str(nodeid)

    async def read_values(self, nodes: Any) -> list[Any]:
        index = self.reads
        self.reads += 1
        if index in self.fail_reads:
            raise ConnectionError("BadSessionClosed")
        frame = self.frames[min(index, len(self.frames) - 1)]
        return [frame["values"].get(tag) for tag in self.tag_order]


def _frames() -> list[dict[str, Any]]:
    lines = (FIXTURES / "opcua_window.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def _run(cfg: ReportConfig, tags: list[TagInfo], client: FakeClient, clock: FakeClock, **kwargs: Any) -> Any:
    client.tag_order = [t.tag for t in tags]

    def factory(endpoint: str, timeout: float) -> UaClient:
        return client

    return asyncio.run(
        sample(
            cfg.opcua,
            tags,
            client_factory=factory,
            clock=clock.now,
            monotonic=clock.mono,
            sleep=clock.sleep,
            **kwargs,
        )
    )


def test_sampling_reads_flagship_nodes_and_builds_report(
    cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]
) -> None:
    frames = _frames()
    wanted = [tags[t] for t in required_tags(cfg.station, alarms)]
    start = datetime.fromisoformat(frames[0]["ts"].replace("Z", "+00:00"))
    clock = FakeClock(start)
    client = FakeClient(frames)
    series = _run(cfg, wanted, client, clock, minutes=8, interval_s=10)
    assert client.connected and client.disconnected
    assert client.reads == len(frames) == 49
    assert client.node_ids[0] == tags[cfg.station.level_tag].opcua_node_id
    assert all(nid.startswith("ns=4;s=|var|CODESYS Control Win V3.Application.") for nid in client.node_ids)
    assert len(series.get("LT101.Value")) == 49

    tz = MSK
    span = series.time_range()
    assert span is not None
    report = build_report(
        series,
        cfg.station,
        tags,
        alarms,
        floor_hour(span[0], tz),
        ceil_hour(span[1], tz),
        "opcua",
        GENERATED_AT,
        data_end=span[1] + timedelta(seconds=10),
    )
    assert len(report.hours) == 1
    hour = report.hours[0]
    assert hour.coverage == pytest.approx(8 / 60 + 10 / 3600, abs=1e-6)  # 49 опросов, удержание последнего 10 с
    assert hour.level_min_m is not None and hour.level_max_m is not None
    assert 0.0 < hour.level_min_m <= hour.level_max_m < 5.0


def test_user_password_security_and_namespace_uri(cfg: ReportConfig, tags: dict[str, TagInfo]) -> None:
    ua = replace(
        cfg.opcua,
        user="report",
        security="Basic256Sha256,SignAndEncrypt,client.der,client_key.pem",
        namespace_uri="urn:kns1:emulator",
    )
    client = FakeClient(_frames())
    clock = FakeClock(datetime(2026, 10, 15, 6, 0, tzinfo=UTC))
    _run(replace(cfg, opcua=ua), [tags["LT101.Value"]], client, clock, minutes=1, interval_s=30, password="pw")
    assert (client.user, client.password) == ("report", "pw")
    assert client.security is not None and client.security.startswith("Basic256Sha256,SignAndEncrypt")
    assert client.ns_uri == "urn:kns1:emulator"
    assert client.node_ids == ["ns=7;s=|var|CODESYS Control Win V3.Application.GVL_Devices.fbLT101.stSts.rValue_eu"]
    assert client.reads == 3


def test_read_failures_skip_polls_then_stop(cfg: ReportConfig, tags: dict[str, TagInfo]) -> None:
    clock = FakeClock(datetime(2026, 10, 15, 6, 0, tzinfo=UTC))
    client = FakeClient(_frames(), fail_reads={1, 2})
    series = _run(cfg, [tags["LT101.Value"]], client, clock, minutes=1, interval_s=10)
    assert client.reads == 7 and len(series.get("LT101.Value")) == 5

    clock = FakeClock(datetime(2026, 10, 15, 6, 0, tzinfo=UTC))
    dead = FakeClient(_frames(), fail_reads=set(range(100)))
    series = _run(cfg, [tags["LT101.Value"]], dead, clock, minutes=60, interval_s=1)
    assert dead.reads == MAX_CONSECUTIVE_FAILURES
    assert len(series) == 0 and dead.disconnected


def test_save_to_writes_loadable_jsonl(cfg: ReportConfig, tags: dict[str, TagInfo], tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 10, 15, 6, 0, tzinfo=UTC))
    client = FakeClient(_frames())
    buffer = io.StringIO()
    wanted = [tags["LT101.Value"], tags["P101.Running"]]
    series = _run(cfg, wanted, client, clock, minutes=0.5, interval_s=10, save_to=buffer)
    path = tmp_path / "s.jsonl"
    path.write_text(buffer.getvalue(), encoding="utf-8")
    loaded = load_jsonl(path)
    assert loaded.series == series.series
    first = json.loads(buffer.getvalue().splitlines()[0])
    assert first["ts"] == "2026-10-15T06:00:00Z"
    assert set(first["values"]) == {"LT101.Value", "P101.Running"}


def test_invalid_interval_rejected(cfg: ReportConfig, tags: dict[str, TagInfo]) -> None:
    clock = FakeClock(datetime(2026, 10, 15, 6, 0, tzinfo=UTC))
    with pytest.raises(ValueError):
        _run(cfg, [tags["LT101.Value"]], FakeClient(_frames()), clock, minutes=1, interval_s=0)
