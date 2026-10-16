"""Источник InfluxDB: текст Flux, разбор annotated CSV, HTTP-запрос через подменный транспорт."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from kns_report.config import ReportConfig
from kns_report.influx import (
    InfluxError,
    build_alarm_flux,
    build_flux,
    fetch,
    is_plaintext_remote,
    load_catalog,
    metric_for,
    parse_annotated_csv,
    query,
    rows_to_activations,
    rows_to_series,
)

from .conftest import MSK

START = datetime(2026, 10, 15, 0, 0, tzinfo=MSK)
STOP = START + timedelta(days=1)

TWO_BLOCKS = """#datatype,string,long,dateTime:RFC3339,double,string,string
#group,false,false,false,false,true,true
#default,_result,,,,,
,result,table,_time,_value,device,metric
,,0,2026-10-14T21:00:00Z,2.31,LT101,level
,,0,2026-10-14T21:00:05.5Z,2.32,LT101,level
,,1,2026-10-14T21:00:00Z,120,FT202,flow

#datatype,string,long,dateTime:RFC3339Nano,boolean,string,string
#group,false,false,false,false,true,true
#default,_result,,,,,
,result,table,_time,_value,device,metric
,,2,2026-10-14T21:00:01.123456789Z,true,P101,running
,,2,2026-10-14T21:10:00Z,false,P101,running

#datatype,string,long,dateTime:RFC3339,long,string,string
#group,false,false,false,false,true,true
#default,_result,,,,,
,result,table,_time,_value,device,metric
,,3,2026-10-14T21:00:00Z,812,P101,starts
,,4,2026-10-14T21:00:00Z,3,LT101,alm_active

"""


def test_flux_has_range_filters_and_keep(cfg: ReportConfig) -> None:
    tags = ["LT101.Value", "P101.Running", "P101.Running", "P101.RunTime"]
    flux = build_flux(cfg.influx, "vodokanal", "kns1", tags, START, STOP)
    assert 'from(bucket: "kns_raw")' in flux
    assert "range(start: 2026-10-14T21:00:00Z, stop: 2026-10-15T21:00:00Z)" in flux
    assert 'r._measurement == "telemetry" and (r._field == "value" or r._field == "quality")' in flux
    assert 'r.site == "vodokanal"' in flux and 'r.area == "kns1"' in flux
    assert 'r.source == "mqtt"' in flux
    assert flux.count('(r.device == "P101" and r.metric == "running")') == 1
    assert '(r.device == "LT101" and r.metric == "level")' in flux
    assert '(r.device == "P101" and r.metric == "run_hours")' in flux
    # недостоверные точки отбрасываются после сведения полей value и quality в строку
    assert 'pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")' in flux
    assert 'filter(fn: (r) => not exists r.quality or not (r.quality == "bad"))' in flux
    assert "map(fn: (r) => ({r with _value: r.value}))" in flux
    assert flux.rstrip().endswith('|> keep(columns: ["_time", "_value", "device", "metric"])')
    assert "aggregateWindow" not in flux


def test_flux_without_quality_and_source(cfg: ReportConfig) -> None:
    influx = replace(cfg.influx, source="opcua", quality_field="")
    flux = build_flux(influx, "vodokanal", "kns1", ["LT101.Value"], START, STOP)
    assert 'r._measurement == "telemetry" and r._field == "value")' in flux
    assert 'r.source == "opcua"' in flux
    assert "pivot" not in flux and "quality" not in flux
    no_source = build_flux(replace(influx, source=""), "", "", ["LT101.Value"], START, STOP)
    assert "r.source" not in no_source and "r.site" not in no_source and "r.area" not in no_source


def test_flux_metric_mapping_downsample_and_quoting(cfg: ReportConfig) -> None:
    influx = replace(
        cfg.influx, metrics={"Value": "value"}, downsample="10s", bucket='kns"x', exclude_quality=("bad", "uncertain")
    )
    flux = build_flux(influx, "", "", ["LT101.Value"], START, STOP)
    assert '(r.device == "LT101" and r.metric == "value")' in flux
    assert 'not (r.quality == "bad" or r.quality == "uncertain")' in flux
    assert "aggregateWindow(every: 10s, fn: last, createEmpty: false)" in flux
    assert flux.index("aggregateWindow") < flux.index("pivot")
    assert 'from(bucket: "kns\\"x")' in flux
    with pytest.raises(ValueError):
        build_flux(influx, "", "", [], START, STOP)


def test_annotated_csv_types_and_blocks() -> None:
    rows = parse_annotated_csv(TWO_BLOCKS)
    assert len(rows) == 7
    assert rows[0]["result"] == "_result"  # значение из #default
    assert rows[0]["_value"] == 2.31 and isinstance(rows[0]["_value"], float)
    assert rows[1]["_time"] == datetime(2026, 10, 14, 21, 0, 5, 500000, tzinfo=UTC)
    assert rows[3]["_value"] is True
    assert rows[3]["_time"].microsecond == 123456
    assert rows[5]["_value"] == 812 and isinstance(rows[5]["_value"], int)


def test_rows_to_series_maps_tags(cfg: ReportConfig) -> None:
    series = rows_to_series(cfg.influx, parse_annotated_csv(TWO_BLOCKS))
    assert series.tags() == ["FT202.Value", "LT101.AlmActive", "LT101.Value", "P101.Running", "P101.Starts"]
    assert metric_for(cfg.influx, "PT201.Value") == "Value"  # нет в отображении — свойство как есть
    assert [v for _, v in series.get("P101.Running")] == [True, False]
    only = rows_to_series(cfg.influx, parse_annotated_csv(TWO_BLOCKS), ["LT101.Value"])
    assert only.tags() == ["LT101.Value"]
    row = {"device": "P101", "metric": "running", "_time": START, "_value": True}
    renamed = rows_to_series(replace(cfg.influx, metrics={"Running": "running"}), [row])
    assert renamed.tags() == ["P101.Running"]  # обратное отображение метрик
    junk: list[dict[str, Any]] = [
        {"device": "P101", "metric": "Value", "_time": START, "_value": "n/a"},
        {"device": None},
    ]
    assert len(rows_to_series(cfg.influx, junk)) == 0


def test_error_table_in_stream_raises() -> None:
    text = "#datatype,string,string\n#group,true,true\n#default,,\n,error,reference\n,bucket not found,\n\n"
    with pytest.raises(InfluxError, match="bucket not found"):
        parse_annotated_csv(text)


def test_query_sends_token_and_json_body(cfg: ReportConfig) -> None:
    calls: list[tuple[str, dict[str, str], bytes, float]] = []

    def transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
        calls.append((url, headers, body, timeout))
        return 200, TWO_BLOCKS.encode()

    result = fetch(
        cfg.influx, "secret-token", "vodokanal", "kns1", ["LT101.Value", "P101.Starts"], START, STOP, transport
    )
    assert len(calls) == 2  # телеметрия и тревоги
    url, headers, body, timeout = calls[0]
    assert url == "http://localhost:8086/api/v2/query?org=vodokanal"
    assert headers["Authorization"] == "Token secret-token"
    assert headers["Accept"] == "application/csv"
    payload = json.loads(body)
    assert payload["type"] == "flux"
    assert payload["dialect"]["annotations"] == ["datatype", "group", "default"]
    assert "range(start: 2026-10-14T21:00:00Z" in payload["query"]
    assert timeout == cfg.influx.timeout_s
    assert result.series.tags() == ["LT101.Value", "P101.Starts"]
    assert result.raw == TWO_BLOCKS
    assert '"alarm"' in json.loads(calls[1][2])["query"]
    assert result.activations == []  # в ответе нет колонки suffix и значений Activated

    words = replace(cfg.influx, alarms="words")
    calls.clear()
    assert fetch(words, "t", "", "", ["LT101.Value"], START, STOP, transport).activations is None
    assert len(calls) == 1


def test_query_http_error_message(cfg: ReportConfig) -> None:
    def unauthorized(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
        return 401, b'{"code":"unauthorized","message":"unauthorized access"}'

    with pytest.raises(InfluxError, match="401: unauthorized access"):
        query(cfg.influx, "bad", 'from(bucket: "x")', unauthorized)

    def broken(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
        return 502, b"<html>Bad Gateway</html>"

    with pytest.raises(InfluxError, match="502"):
        query(cfg.influx, "t", "x", broken)


def test_alarm_flux_and_activations(cfg: ReportConfig) -> None:
    flux = build_alarm_flux(cfg.influx, "vodokanal", "kns1", START, STOP)
    assert 'r._measurement == "alarm" and r._field == "reason"' in flux
    assert 'r._value == "Activated"' in flux
    assert 'keep(columns: ["_time", "_value", "device", "suffix"])' in flux
    text = (
        "#datatype,string,long,dateTime:RFC3339,string,string,string\n"
        "#group,false,false,false,false,true,true\n#default,_result,,,,,\n"
        ",result,table,_time,_value,device,suffix\n"
        ",,0,2026-10-15T11:55:50Z,Activated,LT101,HH\n"
        ",,0,2026-10-15T12:10:00Z,Cleared,LT101,HH\n"
        ",,1,2026-10-15T07:05:00Z,Activated,ZS404,ALM\n\n"
    )
    assert rows_to_activations(cfg.influx, parse_annotated_csv(text)) == [
        (datetime(2026, 10, 15, 7, 5, tzinfo=UTC), "ZS404.ALM"),
        (datetime(2026, 10, 15, 11, 55, 50, tzinfo=UTC), "LT101.HH"),
    ]


def test_catalog_mapping(tmp_path: Path) -> None:
    catalog = tmp_path / "telemetry_catalog.csv"
    catalog.write_text(
        "# каталог\ndevice;metric;scada_tag;kind\n"
        "LT101;level;LT101.Value;analog\nP101;run_hours;P101.RunTime;counter\n",
        encoding="utf-8",
    )
    assert load_catalog(catalog) == {"LT101.Value": "level", "P101.RunTime": "run_hours"}
    empty = tmp_path / "empty.csv"
    empty.write_text("device;metric\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_catalog(empty)


@pytest.mark.parametrize(
    ("url", "plain"),
    [
        ("http://localhost:8086", False),
        ("http://127.0.0.1:8086", False),
        ("https://influx.example.local:8086", False),
        ("http://10.0.20.5:8086", True),
    ],
)
def test_plaintext_remote_detection(url: str, plain: bool) -> None:
    assert is_plaintext_remote(url) is plain
