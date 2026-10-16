"""Командная строка: режимы file, influx (подменный HTTP) и opcua (подменный опрос)."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import kns_report.cli as cli
import kns_report.opcua_source as opcua_source
from kns_report import influx
from kns_report.config import load_config, read_env_file
from kns_report.samples import SeriesSet, load_jsonl

from .conftest import FIXTURES

FIXTURE_CSV = (FIXTURES / "influx_day.csv").read_text(encoding="utf-8")
FIXTURE_ALARMS = (FIXTURES / "influx_day_alarms.csv").read_text(encoding="utf-8")
NOW = datetime(2026, 10, 16, 6, 30, tzinfo=UTC)  # 09:30 МСК 16.10 — «вчера» = 15.10


def _run(argv: list[str]) -> int:
    args = cli.build_parser().parse_args(argv)
    return cli.run(args, now=NOW)


def test_file_mode_influx_csv(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = _run(["file", str(FIXTURES / "influx_day.csv"), "--date", "2026-10-15", "--out-dir", str(tmp_path)])
    assert code == 0
    printed = capsys.readouterr().out.split()
    names = sorted(Path(p).name for p in printed)
    assert names == ["kns1_daily_2026-10-15.csv", "kns1_daily_2026-10-15.xlsx", "kns1_daily_2026-10-15_alarms.csv"]
    rows = list(csv.DictReader((tmp_path / "kns1_daily_2026-10-15.csv").open(encoding="utf-8"), delimiter=";"))
    assert len(rows) == 24
    assert sum(int(r["alarms_total"]) for r in rows) == 4  # события из соседнего influx_day_alarms.csv


def test_file_mode_csv_without_alarm_events(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    lone = tmp_path / "day.csv"
    lone.write_text(FIXTURE_CSV, encoding="utf-8")
    assert _run(["file", str(lone), "--date", "2026-10-15", "--out-dir", str(tmp_path), "--formats", "csv"]) == 0
    assert "day_alarms.csv" in caplog.text
    rows = list(csv.DictReader((tmp_path / "kns1_daily_2026-10-15.csv").open(encoding="utf-8"), delimiter=";"))
    assert sum(int(r["alarms_total"]) for r in rows) == 0


def test_catalog_option(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.csv"
    catalog.write_text("device;metric;scada_tag\nLT101;tank_level;LT101.Value\n", encoding="utf-8")
    code = _run(
        [
            "file",
            str(FIXTURES / "influx_day.csv"),
            "--date",
            "2026-10-15",
            "--catalog",
            str(catalog),
            "--out-dir",
            str(tmp_path),
            "--formats",
            "csv",
        ]
    )
    assert code == 0
    rows = list(csv.DictReader((tmp_path / "kns1_daily_2026-10-15.csv").open(encoding="utf-8"), delimiter=";"))
    assert rows[0]["level_avg_m"] == ""  # в файле метрика level, каталог ждёт tank_level


def test_file_mode_jsonl_period_from_data(tmp_path: Path) -> None:
    code = _run(["file", str(FIXTURES / "opcua_window.jsonl"), "--out-dir", str(tmp_path), "--formats", "csv"])
    assert code == 0
    rows = list(
        csv.DictReader((tmp_path / "kns1_report_2026-10-15_1400-1500.csv").open(encoding="utf-8"), delimiter=";")
    )
    assert len(rows) == 1
    assert float(rows[0]["data_coverage_pct"]) == pytest.approx(100 * (8 * 60 + 10) / 3600, abs=0.05)
    assert not (tmp_path / "kns1_report_2026-10-15_1400-1500.xlsx").exists()


def _fake_transport(seen: list[dict[str, Any]], status: int = 200, body: bytes | None = None) -> influx.Transport:
    def transport(url: str, headers: dict[str, str], payload: bytes, timeout: float) -> tuple[int, bytes]:
        seen.append({"url": url, "headers": headers, "payload": payload})
        if body is not None:
            return status, body
        is_alarm = b'_measurement == \\"alarm\\"' in payload
        return status, (FIXTURE_ALARMS if is_alarm else FIXTURE_CSV).encode()

    return transport


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, transport: influx.Transport) -> None:
    real = influx.fetch

    def fetch(*args: Any, **kwargs: Any) -> influx.InfluxResult:
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(cli, "fetch", fetch)


def test_influx_mode_yesterday_with_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INFLUX_TOKEN", raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "# секреты стенда\nDOCKER_INFLUXDB_INIT_ADMIN_TOKEN='tok-123'\nDOCKER_INFLUXDB_INIT_ORG=kns\n"
        "DOCKER_INFLUXDB_INIT_BUCKET=kns_raw\n",
        encoding="utf-8",
    )
    seen: list[dict[str, Any]] = []
    _patch_fetch(monkeypatch, _fake_transport(seen))
    raw = tmp_path / "raw.csv"
    code = _run(["influx", "--env-file", str(env), "--out-dir", str(tmp_path), "--save-raw", str(raw)])
    assert code == 0
    assert seen[0]["headers"]["Authorization"] == "Token tok-123"
    assert b'from(bucket: \\"kns_raw\\")' in seen[0]["payload"]
    # сутки 15.10 МСК плюс lookback 2 ч для удержания значений с прошлых суток
    assert b"range(start: 2026-10-14T19:00:00Z, stop: 2026-10-15T21:00:00Z)" in seen[0]["payload"]
    assert (tmp_path / "kns1_daily_2026-10-15.xlsx").exists()
    assert raw.read_text(encoding="utf-8") == FIXTURE_CSV
    assert (tmp_path / "raw_alarms.csv").read_text(encoding="utf-8") == FIXTURE_ALARMS
    assert len(seen) == 2 and b'r.area == \\"kns1\\"' in seen[1]["payload"]
    alarms = list(csv.DictReader((tmp_path / "kns1_daily_2026-10-15_alarms.csv").open(encoding="utf-8"), delimiter=";"))
    assert [a["code"] for a in alarms] == ["ZS404.ALM", "P102.FTS", "LT101.H", "LT101.HH"]


def test_influx_mode_stand_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    for name in ("INFLUX_TOKEN", "INFLUX_ADMIN_TOKEN", "INFLUX_ORG", "INFLUX_BUCKET", "INFLUX_URL", "INFLUX_PORT"):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / ".env"
    # ключи — как в .env.example стенда
    lines = ["INFLUX_ADMIN_TOKEN=adm-1", "INFLUX_ORG=vodokanal", "INFLUX_BUCKET=kns_raw", "INFLUX_PORT=18086"]
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    seen: list[dict[str, Any]] = []
    _patch_fetch(monkeypatch, _fake_transport(seen))
    assert _run(["influx", "--date", "2026-10-15", "--env-file", str(env), "--out-dir", str(tmp_path)]) == 0
    assert seen[0]["url"] == "http://localhost:18086/api/v2/query?org=vodokanal"
    assert seen[0]["headers"]["Authorization"] == "Token adm-1"
    assert "токен администратора" in caplog.text
    assert "adm-1" not in caplog.text


def test_influx_mode_env_token_and_explicit_date(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFLUX_TOKEN", "env-token")
    seen: list[dict[str, Any]] = []
    _patch_fetch(monkeypatch, _fake_transport(seen))
    code = _run(["influx", "--date", "2026-10-15", "--url", "http://influxdb:8086", "--out-dir", str(tmp_path)])
    assert code == 0
    assert seen[0]["url"].startswith("http://influxdb:8086/api/v2/query?org=vodokanal")
    assert seen[0]["headers"]["Authorization"] == "Token env-token"


def test_influx_mode_without_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INFLUX_TOKEN", raising=False)
    monkeypatch.delenv("DOCKER_INFLUXDB_INIT_ADMIN_TOKEN", raising=False)
    assert _run(["influx", "--out-dir", str(tmp_path)]) == 2


def test_main_reports_influx_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INFLUX_TOKEN", "bad")
    _patch_fetch(monkeypatch, _fake_transport([], 401, b'{"message":"unauthorized access"}'))
    assert cli.main(["influx", "--date", "2026-10-15", "--out-dir", str(tmp_path)]) == 1


def test_opcua_mode_uses_sampler(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPCUA_PASSWORD", "ua-secret")
    calls: dict[str, Any] = {}

    def fake_sample(cfg: Any, tags: list[Any], **kwargs: Any) -> SeriesSet:
        calls.update(kwargs, cfg=cfg, n_tags=len(tags))
        return load_jsonl(FIXTURES / "opcua_window.jsonl")

    monkeypatch.setattr(opcua_source, "sample_to_file", fake_sample)
    code = _run(
        [
            "opcua",
            "--endpoint",
            "opc.tcp://plc:4840",
            "--minutes",
            "8",
            "--interval",
            "10",
            "--user",
            "report",
            "--out-dir",
            str(tmp_path),
            "--formats",
            "xlsx",
        ]
    )
    assert code == 0
    assert calls["cfg"].endpoint == "opc.tcp://plc:4840" and calls["cfg"].user == "report"
    assert calls["password"] == "ua-secret"
    assert (calls["minutes"], calls["interval_s"]) == (8.0, 10.0)
    assert calls["n_tags"] == 2 + 3 * 3 + 27  # уровень, расход, 3 × (Running, Starts, RunTime), AlmActive устройств
    rows = (
        list(csv.DictReader((tmp_path / "kns1_report_2026-10-15_1400-1500.csv").open(encoding="utf-8"), delimiter=";"))
        if (tmp_path / "kns1_report_2026-10-15_1400-1500.csv").exists()
        else []
    )
    assert rows == []  # запрошен только xlsx
    assert (tmp_path / "kns1_report_2026-10-15_1400-1500.xlsx").exists()


def test_bad_format_is_usage_error() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["file", "x.jsonl", "--formats", "pdf"])
    assert exc.value.code == 2


def test_config_override_and_env_parser(tmp_path: Path) -> None:
    custom = tmp_path / "my.toml"
    custom.write_text(
        '[station]\nname = "КНС-2"\npumps = ["P101"]\n[influx.metrics]\nValue = "value"\n', encoding="utf-8"
    )
    cfg = load_config(custom)
    assert cfg.station.name == "КНС-2" and cfg.station.pumps == ("P101",)
    assert cfg.station.level_tag == "LT101.Value"
    assert cfg.influx.metrics["Value"] == "value"  # таблица дополняется, а не заменяется
    assert cfg.influx.metrics["LT101.Value"] == "level"
    bad = tmp_path / "bad.toml"
    bad.write_text("[station]\npump_methd = 'auto'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="pump_methd"):
        load_config(bad)
    env = tmp_path / ".env"
    env.write_text('export A="1"\nB = two\n#C=3\nbroken\n', encoding="utf-8")
    assert read_env_file(env) == {"A": "1", "B": "two"}
