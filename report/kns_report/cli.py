"""Командная строка kns-report.

    kns-report influx --date 2026-10-15 --env-file .env       # сутки из InfluxDB 2
    kns-report opcua --minutes 10 --interval 1                # выборка с OPC UA-сервера
    kns-report file samples.jsonl                             # из сохранённой выборки

Результат — `<станция>_daily_<дата>.csv`, `..._alarms.csv` и `.xlsx` в каталоге --out-dir
(по умолчанию build/reports).
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, tzinfo
from pathlib import Path

from kns_report import __version__
from kns_report.aggregate import DailyReport, build_report
from kns_report.config import ReportConfig, StationConfig, load_config, read_env_file, secret
from kns_report.csv_out import write_alarms_csv, write_hourly_csv
from kns_report.influx import (
    InfluxError,
    fetch,
    is_plaintext_remote,
    load_catalog,
    parse_annotated_csv,
    rows_to_activations,
    rows_to_series,
)
from kns_report.samples import SeriesSet, load_jsonl
from kns_report.tagmodel import AlarmDef, alarm_devices, load_alarms, load_tags
from kns_report.timeutil import ceil_hour, day_bounds, floor_hour, parse_tz
from kns_report.xlsx_out import write_xlsx

log = logging.getLogger("kns_report")

FORMATS = ("csv", "xlsx")
# Запасные имена переменных: .env стенда (.env.example) и образа influxdb:2 (DOCKER_INFLUXDB_INIT_*)
INFLUX_FALLBACK_ENV = {
    "token": ("INFLUX_ADMIN_TOKEN", "DOCKER_INFLUXDB_INIT_ADMIN_TOKEN"),
    "org": ("INFLUX_ORG", "DOCKER_INFLUXDB_INIT_ORG"),
    "bucket": ("INFLUX_BUCKET", "DOCKER_INFLUXDB_INIT_BUCKET"),
    "url": ("INFLUX_URL",),
}
ALARMS_SUFFIX = "_alarms"


def required_tags(station: StationConfig, alarms: list[AlarmDef], alarm_words: bool = True) -> list[str]:
    """Теги SCADA, которые нужны отчёту; alarm_words — и слова тревог `<DEV>.AlmActive`."""
    tags = [station.level_tag, station.flow_tag]
    for pump in station.pumps:
        tags += [f"{pump}.Running", f"{pump}.Starts", f"{pump}.RunTime"]
    if alarm_words:
        devices = list(station.alarm_devices) or alarm_devices(alarms)
        tags += [f"{device}.AlmActive" for device in devices]
    return tags


def _parse_formats(text: str) -> list[str]:
    formats = [f.strip().lower() for f in text.split(",") if f.strip()]
    bad = [f for f in formats if f not in FORMATS]
    if bad or not formats:
        raise argparse.ArgumentTypeError(f"форматы: {', '.join(FORMATS)}")
    return formats


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path, help="TOML с настройками (поверх встроенных)")
    common.add_argument("--tz", help="часовой пояс отчёта: +03:00, UTC или имя IANA")
    common.add_argument("--out-dir", type=Path, default=Path("build/reports"), help="каталог результата")
    common.add_argument("--formats", type=_parse_formats, default=list(FORMATS), help="csv,xlsx (по умолчанию оба)")
    common.add_argument("--tags-csv", type=Path, help="scada_tags.csv iolistgen (по умолчанию встроенный)")
    common.add_argument("--alarms-csv", type=Path, help="scada_alarms.csv iolistgen (по умолчанию встроенный)")
    common.add_argument("--catalog", type=Path, help="schema/telemetry_catalog.csv: метрики InfluxDB для тегов")
    common.add_argument("-v", "--verbose", action="store_true", help="подробный журнал")

    parser = argparse.ArgumentParser(
        prog="kns-report",
        description="Суточный отчёт КНС-1 по данным InfluxDB 2 или OPC UA: CSV и XLSX",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    influx = sub.add_parser("influx", parents=[common], help="сутки из InfluxDB 2 (Flux, HTTP API)")
    influx.add_argument("--date", type=date.fromisoformat, help="дата ГГГГ-ММ-ДД (по умолчанию — вчера)")
    influx.add_argument("--url", help="адрес InfluxDB, например http://localhost:8086")
    influx.add_argument("--org", help="организация InfluxDB")
    influx.add_argument("--bucket", help="бакет InfluxDB")
    influx.add_argument("--env-file", type=Path, help=".env с INFLUX_TOKEN (или DOCKER_INFLUXDB_INIT_ADMIN_TOKEN)")
    influx.add_argument(
        "--save-raw", type=Path, help="сохранить ответы InfluxDB (annotated CSV; тревоги — в <имя>_alarms.csv)"
    )

    opcua = sub.add_parser("opcua", parents=[common], help="выборка с OPC UA-сервера ПЛК или эмулятора")
    opcua.add_argument("--endpoint", help="opc.tcp://узел:4840")
    opcua.add_argument("--minutes", type=float, help="длительность выборки, мин")
    opcua.add_argument("--interval", type=float, help="период опроса, с")
    opcua.add_argument("--user", help="пользователь OPC UA (пароль — переменная OPCUA_PASSWORD)")
    opcua.add_argument("--security", help="строка безопасности asyncua: Basic256Sha256,SignAndEncrypt,cert,key")
    opcua.add_argument("--env-file", type=Path, help=".env с OPCUA_USERNAME и OPCUA_PASSWORD")
    opcua.add_argument("--save-samples", type=Path, help="записать выборку в JSON Lines")

    from_file = sub.add_parser(
        "file", parents=[common], help="из сохранённой выборки (.jsonl) или ответа InfluxDB (.csv)"
    )
    from_file.add_argument("path", type=Path)
    from_file.add_argument("--date", type=date.fromisoformat, help="сутки отчёта (по умолчанию — по данным)")
    from_file.add_argument(
        "--alarm-events", type=Path, help="ответ InfluxDB по тревогам (по умолчанию <имя>_alarms.csv рядом)"
    )
    return parser


def _period_from_data(series: SeriesSet, tz: tzinfo) -> tuple[datetime, datetime]:
    span = series.time_range()
    if span is None:
        raise ValueError("в данных нет ни одной точки")
    start = floor_hour(span[0], tz)
    end = ceil_hour(span[1], tz)
    if end <= start:
        end = start + timedelta(hours=1)
    return start, end


def output_stem(report: DailyReport) -> str:
    start, end = report.period_start, report.period_end
    if start.hour == 0 and end - start == timedelta(days=1):
        return f"{report.station_code}_daily_{start:%Y-%m-%d}"
    return f"{report.station_code}_report_{start:%Y-%m-%d_%H%M}-{end:%H%M}"


def write_outputs(report: DailyReport, out_dir: Path, formats: list[str]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = output_stem(report)
    written = []
    if "csv" in formats:
        hourly = out_dir / f"{stem}.csv"
        alarms = out_dir / f"{stem}{ALARMS_SUFFIX}.csv"
        write_hourly_csv(report, hourly)
        write_alarms_csv(report, alarms)
        written += [hourly, alarms]
    if "xlsx" in formats:
        xlsx = out_dir / f"{stem}.xlsx"
        write_xlsx(report, xlsx)
        written.append(xlsx)
    return written


def _sibling(path: Path) -> Path:
    return path.with_name(f"{path.stem}{ALARMS_SUFFIX}{path.suffix}")


def _with_catalog(cfg: ReportConfig, catalog: Path | None) -> ReportConfig:
    if catalog is None:
        return cfg
    metrics = {**cfg.influx.metrics, **load_catalog(catalog)}
    return replace(cfg, influx=replace(cfg.influx, metrics=metrics))


def run(args: argparse.Namespace, now: datetime | None = None) -> int:
    cfg = _with_catalog(load_config(args.config), args.catalog)
    if args.tz:
        cfg = replace(cfg, station=replace(cfg.station, timezone=args.tz))
    tz = parse_tz(cfg.station.timezone)
    tags = load_tags(args.tags_csv)
    alarms = load_alarms(args.alarms_csv)
    now = now or datetime.now(UTC)
    events_mode = cfg.influx.alarms == "events"
    activations: list[tuple[datetime, str]] | None = None
    data_end: datetime | None

    if args.command == "influx":
        env = read_env_file(args.env_file) if args.env_file else {}
        port = secret("", env, "INFLUX_PORT")
        influx = replace(
            cfg.influx,
            url=args.url
            or secret("", env, *INFLUX_FALLBACK_ENV["url"])
            or (f"http://localhost:{port}" if port else cfg.influx.url),
            org=args.org or secret("", env, *INFLUX_FALLBACK_ENV["org"]) or cfg.influx.org,
            bucket=args.bucket or secret("", env, *INFLUX_FALLBACK_ENV["bucket"]) or cfg.influx.bucket,
        )
        token = secret(influx.token_env, env, *INFLUX_FALLBACK_ENV["token"])
        if token and not secret(influx.token_env, env):
            log.warning("токен администратора InfluxDB из .env: для регулярных отчётов выдайте токен только на чтение")
        if not token:
            log.error("нет токена InfluxDB: задайте переменную %s или --env-file", influx.token_env)
            return 2
        if is_plaintext_remote(influx.url):
            log.warning("InfluxDB по http:// не на локальном узле: токен передаётся открытым текстом")
        day = args.date or (now.astimezone(tz).date() - timedelta(days=1))
        start, end = day_bounds(day, tz)
        lookback = max(cfg.station.analog_max_gap, cfg.station.discrete_max_gap)
        wanted = required_tags(cfg.station, alarms, alarm_words=not events_mode)
        result = fetch(influx, token, cfg.station.site, cfg.station.area, wanted, start - lookback, end)
        series, activations = result.series, result.activations
        if args.save_raw:
            args.save_raw.parent.mkdir(parents=True, exist_ok=True)
            args.save_raw.write_text(result.raw, encoding="utf-8", newline="\n")
            if result.raw_alarms is not None:
                _sibling(args.save_raw).write_text(result.raw_alarms, encoding="utf-8", newline="\n")
        source = f"InfluxDB {influx.url}, бакет {influx.bucket}"
        data_end = min(now, end)
    elif args.command == "opcua":
        from kns_report.opcua_source import sample_to_file

        env = read_env_file(args.env_file) if args.env_file else {}
        ua = replace(
            cfg.opcua,
            endpoint=args.endpoint or cfg.opcua.endpoint,
            user=args.user if args.user is not None else (cfg.opcua.user or secret("", env, "OPCUA_USERNAME") or ""),
            security=args.security if args.security is not None else cfg.opcua.security,
        )
        wanted = required_tags(cfg.station, alarms)
        missing = [t for t in wanted if t not in tags]
        if missing:
            log.error("нет в scada_tags.csv: %s", ", ".join(missing))
            return 2
        password = secret(ua.password_env, env) if ua.user else None
        minutes = args.minutes if args.minutes is not None else ua.minutes
        interval = args.interval if args.interval is not None else ua.interval_s
        if args.save_samples:
            args.save_samples.parent.mkdir(parents=True, exist_ok=True)
        series = sample_to_file(
            ua,
            [tags[t] for t in wanted],
            minutes=minutes,
            interval_s=interval,
            password=password,
            save_path=args.save_samples,
        )
        start, end = _period_from_data(series, tz)
        span = series.time_range()
        data_end = span[1] + timedelta(seconds=interval) if span else None
        source = f"OPC UA {ua.endpoint}, выборка {minutes:g} мин с шагом {interval:g} с"
    else:
        path: Path = args.path
        if path.suffix.lower() == ".csv":
            wanted = required_tags(cfg.station, alarms, alarm_words=not events_mode)
            series = rows_to_series(cfg.influx, parse_annotated_csv(path.read_text(encoding="utf-8")), wanted)
            events_file = args.alarm_events or _sibling(path)
            if events_mode and events_file.exists():
                activations = rows_to_activations(
                    cfg.influx, parse_annotated_csv(events_file.read_text(encoding="utf-8"))
                )
            elif events_mode:
                log.warning("нет файла событий тревог %s — тревоги в отчёт не попадут", events_file.name)
                activations = []
        else:
            series = load_jsonl(path)
        if args.date:
            start, end = day_bounds(args.date, tz)
        else:
            start, end = _period_from_data(series, tz)
        source = f"файл {path.name}"
        # выборка OPC UA обрывается на последнем опросе; ответ InfluxDB — на конце суток или «сейчас»
        data_end = series.horizon() if path.suffix.lower() == ".jsonl" else min(now, end)

    report = build_report(series, cfg.station, tags, alarms, start, end, source, now, data_end, activations)
    for warning in report.warnings:
        log.warning("%s", warning)
    for out in write_outputs(report, args.out_dir, args.formats):
        print(out)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    # Консоль Windows (cp1251/cp866) не печатает часть символов UTF-8 — заменяем, а не падаем
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    # asyncua пишет каждое чтение на уровне INFO — без -v оставить только предупреждения
    logging.getLogger("asyncua").setLevel(logging.DEBUG if args.verbose else logging.WARNING)
    try:
        return run(args)
    except InfluxError as exc:
        log.error("%s", exc)
        return 1
    except (OSError, ValueError) as exc:
        log.error("%s", exc)
        return 1
