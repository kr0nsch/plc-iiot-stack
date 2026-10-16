"""Источник InfluxDB 2: запрос Flux через HTTP API и разбор annotated CSV.

Запрос — POST /api/v2/query?org=<org> с заголовком `Authorization: Token <токен>`. Токен
берётся из переменной окружения (по умолчанию INFLUX_TOKEN) или из .env и никуда не выводится.
Ответ — annotated CSV (строки #datatype, #group, #default, затем заголовок и данные; таблицы
разделены пустой строкой).

Телеметрия в базе (docs/data_schema.md): measurement `telemetry`, поле `value`, теги из сегментов
топика `vodokanal/kns1/station/<device>/<metric>` — site, area, unit, device, metric. Тег SCADA
`<DEV>.<свойство>` ↔ device = <DEV>, metric — по [influx.metrics] или schema/telemetry_catalog.csv
(LT101.Value → level, P101.RunTime → run_hours). Тревоги — measurement `alarm` из топиков
`.../<device>/alarm/<SUFFIX>`: срабатывание — точка поля reason со значением Activated.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from kns_report.config import InfluxConfig
from kns_report.samples import SeriesSet
from kns_report.timeutil import parse_duration, parse_rfc3339, to_rfc3339_utc

# (url, заголовки, тело, таймаут, с) → (HTTP-статус, тело ответа)
Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


class InfluxError(RuntimeError):
    """Ошибка запроса к InfluxDB (HTTP-статус или ошибка в потоке ответа)."""


@dataclass
class InfluxResult:
    """Ответ InfluxDB: ряды телеметрии, срабатывания тревог (режим events) и сырые ответы."""

    series: SeriesSet
    activations: list[tuple[datetime, str]] | None
    raw: str
    raw_alarms: str | None


def split_tag(tag: str) -> tuple[str, str]:
    """Тег "P101.Running" → ("P101", "Running"); тег без точки — (тег, "")."""
    device, _, prop = tag.partition(".")
    return device, prop


def metric_for(cfg: InfluxConfig, tag: str) -> str:
    """Имя метрики в базе: по полному тегу, затем по свойству, иначе — свойство как есть."""
    _, prop = split_tag(tag)
    return cfg.metrics.get(tag, cfg.metrics.get(prop, prop))


def load_catalog(path: Path) -> dict[str, str]:
    """schema/telemetry_catalog.csv → {тег SCADA: метрика} для [influx.metrics]."""
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    result: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO("\n".join(lines)), delimiter=";"):
        tag, metric = (row.get("scada_tag") or "").strip(), (row.get("metric") or "").strip()
        if tag and metric:
            result[tag] = metric
    if not result:
        raise ValueError(f"{path}: нет строк с колонками scada_tag и metric")
    return result


def _flux_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _scope_filters(cfg: InfluxConfig, site: str, area: str) -> list[str]:
    lines = []
    if site and cfg.site_tag:
        lines.append(f"  |> filter(fn: (r) => r.{cfg.site_tag} == {_flux_string(site)})")
    if area and cfg.area_tag:
        lines.append(f"  |> filter(fn: (r) => r.{cfg.area_tag} == {_flux_string(area)})")
    return lines


def _range(start: datetime, stop: datetime) -> str:
    return f"  |> range(start: {to_rfc3339_utc(start)}, stop: {to_rfc3339_utc(stop)})"


def build_flux(cfg: InfluxConfig, site: str, area: str, tags: Iterable[str], start: datetime, stop: datetime) -> str:
    """Запрос телеметрии: все нужные ряды за [start, stop) одним запросом."""
    pairs = sorted({(split_tag(tag)[0], metric_for(cfg, tag)) for tag in tags})
    if not pairs:
        raise ValueError("не задано ни одного тега")
    conditions = " or\n      ".join(
        f"(r.{cfg.device_tag} == {_flux_string(d)} and r.{cfg.metric_tag} == {_flux_string(m)})" for d, m in pairs
    )
    quality = bool(cfg.quality_field and cfg.exclude_quality)
    fields = f"r._field == {_flux_string(cfg.field)}"
    if quality:
        fields = f"({fields} or r._field == {_flux_string(cfg.quality_field)})"
    lines = [
        f"from(bucket: {_flux_string(cfg.bucket)})",
        _range(start, stop),
        f"  |> filter(fn: (r) => r._measurement == {_flux_string(cfg.measurement)} and {fields})",
        *_scope_filters(cfg, site, area),
    ]
    if cfg.source_tag and cfg.source:
        lines.append(f"  |> filter(fn: (r) => r.{cfg.source_tag} == {_flux_string(cfg.source)})")
    lines.append(f"  |> filter(fn: (r) =>\n      {conditions})")
    if cfg.downsample:
        every = parse_duration(cfg.downsample)
        lines.append(f"  |> aggregateWindow(every: {int(every.total_seconds())}s, fn: last, createEmpty: false)")
    if quality:
        # значение и достоверность — поля одной точки: свести в строку и отбросить недостоверные
        bad = " or ".join(f"r.{cfg.quality_field} == {_flux_string(q)}" for q in cfg.exclude_quality)
        lines += [
            '  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")',
            f"  |> filter(fn: (r) => not exists r.{cfg.quality_field} or not ({bad}))",
            f"  |> map(fn: (r) => ({{r with _value: r.{cfg.field}}}))",
        ]
    lines.append(f'  |> keep(columns: ["_time", "_value", "{cfg.device_tag}", "{cfg.metric_tag}"])')
    return "\n".join(lines) + "\n"


def build_alarm_flux(cfg: InfluxConfig, site: str, area: str, start: datetime, stop: datetime) -> str:
    """Запрос срабатываний тревог (режим events): точки reason == Activated за [start, stop)."""
    lines = [
        f"from(bucket: {_flux_string(cfg.bucket)})",
        _range(start, stop),
        f"  |> filter(fn: (r) => r._measurement == {_flux_string(cfg.alarm_measurement)}"
        f" and r._field == {_flux_string(cfg.alarm_field)})",
        *_scope_filters(cfg, site, area),
        f"  |> filter(fn: (r) => r._value == {_flux_string(cfg.alarm_value)})",
        f'  |> keep(columns: ["_time", "_value", "{cfg.device_tag}", "{cfg.alarm_suffix_tag}"])',
    ]
    return "\n".join(lines) + "\n"


def _convert(text: str, datatype: str) -> Any:
    if text == "":
        return None
    if datatype == "double":
        return float(text)
    if datatype in ("long", "unsignedLong"):
        return int(text)
    if datatype == "boolean":
        return text.lower() == "true"
    if datatype.startswith("dateTime"):
        return parse_rfc3339(text)
    return text


def parse_annotated_csv(text: str) -> list[dict[str, Any]]:
    """Annotated CSV InfluxDB → список строк {колонка: типизированное значение}."""
    rows: list[dict[str, Any]] = []
    datatypes: list[str] | None = None
    defaults: list[str] | None = None
    header: list[str] | None = None
    for record in csv.reader(io.StringIO(text)):
        if not record or all(cell == "" for cell in record):
            datatypes, defaults, header = None, None, None
            continue
        first = record[0]
        if first.startswith("#"):
            if first == "#datatype":
                datatypes, header = record[1:], None
            elif first == "#default":
                defaults = record[1:]
            continue
        if header is None:
            header = record[1:]
            continue
        cells = record[1:]
        if "error" in header:
            message = cells[header.index("error")] if len(cells) > header.index("error") else ""
            raise InfluxError(f"ошибка в ответе InfluxDB: {message}")
        row: dict[str, Any] = {}
        for index, column in enumerate(header):
            cell = cells[index] if index < len(cells) else ""
            if cell == "" and defaults is not None and index < len(defaults):
                cell = defaults[index]
            dtype = datatypes[index] if datatypes is not None and index < len(datatypes) else "string"
            row[column] = _convert(cell, dtype)
        rows.append(row)
    return rows


def rows_to_series(cfg: InfluxConfig, rows: Iterable[dict[str, Any]], wanted: Iterable[str] | None = None) -> SeriesSet:
    """Строки ответа → ряды по тегам SCADA (обратное отображение метрик).

    С wanted берутся только эти теги (пара device/metric однозначно задаёт тег); без wanted —
    тег по обратному отображению [influx.metrics]: полные теги, затем свойства.
    """
    by_pair = {(split_tag(tag)[0], metric_for(cfg, tag)): tag for tag in wanted} if wanted is not None else None
    full = {(split_tag(key)[0], metric): key for key, metric in cfg.metrics.items() if "." in key}
    reverse = {metric: prop for prop, metric in cfg.metrics.items() if "." not in prop}
    result = SeriesSet()
    for row in rows:
        device = row.get(cfg.device_tag)
        metric = row.get(cfg.metric_tag)
        ts = row.get("_time")
        value = row.get("_value")
        if not isinstance(device, str) or not isinstance(metric, str) or not isinstance(ts, datetime):
            continue
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                continue
        if not isinstance(value, bool | int | float):
            continue
        if by_pair is not None:
            tag = by_pair.get((device, metric))
            if tag is None:
                continue
        else:
            tag = full.get((device, metric)) or f"{device}.{reverse.get(metric, metric)}"
        result.add(tag, ts, value)
    return result.sort()


def rows_to_activations(cfg: InfluxConfig, rows: Iterable[dict[str, Any]]) -> list[tuple[datetime, str]]:
    """Строки ответа на запрос тревог → [(время, код <DEV>.<SUFFIX>)] по времени."""
    result = []
    for row in rows:
        device = row.get(cfg.device_tag)
        suffix = row.get(cfg.alarm_suffix_tag)
        ts = row.get("_time")
        if row.get("_value") != cfg.alarm_value:
            continue
        if isinstance(device, str) and isinstance(suffix, str) and isinstance(ts, datetime):
            result.append((ts, f"{device}.{suffix}"))
    return sorted(result)


def urllib_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
    """HTTP POST стандартной библиотекой (без внешних зависимостей)."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), bytes(response.read())
    except urllib.error.HTTPError as exc:
        return int(exc.code), bytes(exc.read())


def is_plaintext_remote(url: str) -> bool:
    """Адрес http:// не на локальном узле: токен уйдёт по сети открытым текстом."""
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1")


def query(
    cfg: InfluxConfig,
    token: str,
    flux: str,
    transport: Transport = urllib_transport,
) -> str:
    """Выполнить запрос Flux, вернуть annotated CSV. Ошибки HTTP → InfluxError."""
    url = f"{cfg.url.rstrip('/')}/api/v2/query?{urllib.parse.urlencode({'org': cfg.org})}"
    headers = {
        "Authorization": f"Token {token}",
        "Accept": "application/csv",
        "Content-Type": "application/json",
    }
    body = json.dumps(
        {
            "query": flux,
            "type": "flux",
            "dialect": {"header": True, "delimiter": ",", "annotations": ["datatype", "group", "default"]},
        }
    ).encode("utf-8")
    status, payload = transport(url, headers, body, cfg.timeout_s)
    text = payload.decode("utf-8", errors="replace")
    if status != 200:
        message = text.strip()
        with contextlib.suppress(ValueError, AttributeError):
            message = str(json.loads(text).get("message", message))
        raise InfluxError(f"InfluxDB ответил {status}: {message[:300]}")
    return text


def fetch(
    cfg: InfluxConfig,
    token: str,
    site: str,
    area: str,
    tags: list[str],
    start: datetime,
    stop: datetime,
    transport: Transport = urllib_transport,
) -> InfluxResult:
    """Телеметрия тегов за [start, stop) и, в режиме events, срабатывания тревог."""
    text = query(cfg, token, build_flux(cfg, site, area, tags, start, stop), transport)
    series = rows_to_series(cfg, parse_annotated_csv(text), tags)
    if cfg.alarms != "events":
        return InfluxResult(series, None, text, None)
    alarm_text = query(cfg, token, build_alarm_flux(cfg, site, area, start, stop), transport)
    return InfluxResult(series, rows_to_activations(cfg, parse_annotated_csv(alarm_text)), text, alarm_text)
