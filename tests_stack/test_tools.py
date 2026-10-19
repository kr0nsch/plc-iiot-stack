"""Инструменты стенда: генератор конфигурации, make_env, ожидание готовности, Makefile и make.ps1."""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Any

import pytest

import gen_config
import make_env
import send_command
import stack_catalog as sc
import stack_wait


def test_generated_files_are_up_to_date() -> None:
    stale = [p.relative_to(sc.REPO).as_posix() for p in gen_config.stale_files(sc.REPO)]
    assert not stale, f"устарели (python tools_project/gen_config.py): {stale}"


def test_generated_files_are_marked() -> None:
    assert gen_config.GENERATED_BY in (sc.REPO / "telegraf" / "telegraf.d" / "opcua.conf").read_text(encoding="utf-8")
    for path in (sc.REPO / "grafana" / "dashboards").glob("*.json"):
        assert gen_config.GENERATED_BY in path.read_text(encoding="utf-8")


def test_send_command_builds_schema_valid_commands() -> None:
    """send_command.py: каждая команда белого списка — по command.schema.json и текущей версии схемы."""
    for e in sc.load_whitelist():
        value = 50.0 if e.value_type == "number" else None
        body = send_command.build_command(e.command, value, "pytest@tools")
        assert body["schema_version"] == sc.load_topics()["schema_version"]
        assert send_command.schema_errors(body) == [], e
        assert send_command.whitelisted(e.device, e.command)
    assert send_command.schema_errors(send_command.build_command("SpeedSp", 140.0, "pytest@tools"))
    assert not send_command.whitelisted("P101", "SetOos")


def test_make_env_creates_and_extends(tmp_path: Path) -> None:
    example = tmp_path / ".env.example"
    example.write_text("# comment\nA_USER=plc\nA_PASSWORD=change-me\nINFLUX_ADMIN_TOKEN=change-me\n", encoding="utf-8")
    target = tmp_path / ".env"
    added = make_env.make_env(example, target)
    assert added == ["A_USER", "A_PASSWORD", "INFLUX_ADMIN_TOKEN"]
    values = make_env.parse_keys(target.read_text(encoding="utf-8"))
    assert values["A_USER"] == "plc"
    assert values["A_PASSWORD"] != "change-me" and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{31}", values["A_PASSWORD"])
    assert len(values["INFLUX_ADMIN_TOKEN"]) == 64
    # Повторный запуск не меняет существующие значения и дописывает новые ключи
    example.write_text(example.read_text(encoding="utf-8") + "B_SECRET=change-me\nB_PORT=1\n", encoding="utf-8")
    assert make_env.make_env(example, target) == ["B_SECRET", "B_PORT"]
    again = make_env.parse_keys(target.read_text(encoding="utf-8"))
    assert again["A_PASSWORD"] == values["A_PASSWORD"] and again["B_PORT"] == "1"
    assert again["B_SECRET"] != "change-me"
    assert make_env.make_env(example, target) == []


@pytest.mark.skipif(os.name != "posix", reason="права файла POSIX")
def test_make_env_secrets_file_is_owner_only(tmp_path: Path) -> None:
    example = tmp_path / ".env.example"
    example.write_text("A_PASSWORD=change-me\n", encoding="utf-8")
    target = tmp_path / ".env"
    old_umask = os.umask(0o022)
    try:
        make_env.make_env(example, target)
    finally:
        os.umask(old_umask)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    # Уже существующий файл с открытыми правами закрывается при пополнении
    os.chmod(target, 0o644)
    make_env.make_env(example, target)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


@pytest.mark.parametrize("key", ["MQTT_PLC_PASSWORD", "INFLUX_ADMIN_TOKEN"])
def test_random_secret_never_starts_with_dash(key: str) -> None:
    assert all(make_env.random_secret(key)[0].isalnum() for _ in range(200))


def test_health_problems() -> None:
    ok: list[dict[str, Any]] = [
        {"Service": s, "State": "running", "Health": "healthy"}
        for s in ("mosquitto", "influxdb", "telegraf", "grafana")
    ]
    done: dict[str, Any] = {"Service": "influxdb-init", "State": "exited", "ExitCode": 0}
    assert stack_wait.health_problems([*ok, done], stack_wait.LONG_RUNNING) == []
    starting: list[dict[str, Any]] = [*ok[:3], {"Service": "grafana", "State": "running", "Health": "starting"}, done]
    assert stack_wait.health_problems(starting, stack_wait.LONG_RUNNING) == ["grafana: running/starting"]
    with pytest.raises(RuntimeError):
        stack_wait.health_problems([*ok, {**done, "ExitCode": 1}], stack_wait.LONG_RUNNING)
    assert "emulator: не запущен" in stack_wait.health_problems([*ok, done], [*stack_wait.LONG_RUNNING, "emulator"])


def test_count_from_annotated_csv() -> None:
    text = (
        "#group,false,false,true,true,false,true\n"
        "#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,long,string\n"
        "#default,_result,,,,,\n"
        ",result,table,_start,_stop,_value,source\n"
        ",,0,2026-10-16T08:00:00Z,2026-10-16T08:10:00Z,12,mqtt\n"
        ",,1,2026-10-16T08:00:00Z,2026-10-16T08:10:00Z,3,opcua\n"
        "\n"
    )
    assert stack_wait.count_from_csv(text) == 15
    assert stack_wait.count_from_csv("") == 0


def test_wait_counts_only_fresh_telemetry() -> None:
    """Ожидание данных не засчитывает точки прошлого запуска, оставшиеся в томе InfluxDB."""
    flux = stack_wait.telemetry_flux("kns_raw", 1792137600.0)
    assert "range(start: 2026-10-16T08:00:00Z)" in flux
    assert "-10m" not in flux
    assert stack_wait.rfc3339(0) == "1970-01-01T00:00:00Z"
    assert 'r._value == "online"' in stack_wait.birth_flux("kns_raw")


def test_makefile_recipes_use_tabs_and_cover_targets() -> None:
    text = (sc.REPO / "Makefile").read_text(encoding="utf-8")
    targets = set(re.findall(r"^([a-z-]+):", text, re.M))
    assert {"up", "demo", "down", "test", "env", "certs", "clean", "test-stack"} <= targets
    for line in text.splitlines():
        assert not line.startswith("    "), f"рецепт Makefile с пробелами вместо табуляции: {line!r}"


def test_make_ps1_mirrors_makefile() -> None:
    raw = (sc.REPO / "tools_project" / "make.ps1").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "make.ps1 — UTF-8 с BOM для Windows PowerShell 5.1"
    text = raw.decode("utf-8-sig")
    match = re.search(r"ValidateSet\(([^)]*)\)", text)
    assert match
    ps_targets = {t.strip().strip("'") for t in match.group(1).split(",")}
    mk_targets = set(re.findall(r"^([a-z-]+):", (sc.REPO / "Makefile").read_text(encoding="utf-8"), re.M))
    assert ps_targets == mk_targets
    assert "&&" not in text and "??" not in text, "синтаксис PowerShell 7 недоступен в Windows PowerShell 5.1"
