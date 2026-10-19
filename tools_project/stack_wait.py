"""Ожидание готовности стенда: сервисы docker compose здоровы, данные дошли до InfluxDB и Grafana.

Назначение: ``make up`` (``--health``) и ``make demo`` (``--data``), то же в ``make.ps1``.
Автор: kr0nsch. Версия: 1.0. Описание стенда — docs/ARCHITECTURE.md.

Проверки ``--data`` (критерий «данные на дашбордах»):
1. в InfluxDB есть свежая телеметрия LT101/level — с отметкой времени после начала ожидания (с запасом
   5 с на расхождение часов): данные прошлого запуска в томе не засчитываются (запрос influx CLI внутри
   контейнера influxdb — порт базы на хост не публикуется);
2. узел PLC1 сообщил о рождении (node_status = online);
3. Grafana отвечает и видит три дашборда КНС-1 (HTTP API, логин из .env).
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from make_env import parse_keys

ROOT = Path(__file__).resolve().parent.parent
LONG_RUNNING = ("mosquitto", "influxdb", "telegraf", "grafana")
ONE_SHOT = ("influxdb-init",)
DASHBOARD_UIDS = ("kns1-overview", "kns1-pumps", "kns1-alarms")


def compose_cmd(files: Sequence[str]) -> list[str]:
    cmd = ["docker", "compose"]
    for f in files or ["docker-compose.yml"]:
        cmd += ["-f", f]
    return cmd


def run(cmd: Sequence[str], timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(cmd), cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=timeout)


def compose_ps(files: Sequence[str]) -> list[dict[str, Any]]:
    """Состояние контейнеров: JSON по строке (Compose 2.21+) или массивом (старые версии)."""
    res = run([*compose_cmd(files), "ps", "--all", "--format", "json"])
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "docker compose ps завершился с ошибкой")
    text = res.stdout.strip()
    if not text:
        return []
    if text.startswith("["):
        data: list[dict[str, Any]] = json.loads(text)
        return data
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def health_problems(containers: list[dict[str, Any]], services: Sequence[str]) -> list[str]:
    """Что ещё не готово: пустой список — все сервисы здоровы, однократные завершились с кодом 0."""
    by_service = {c.get("Service", ""): c for c in containers}
    problems = []
    for name in services:
        c = by_service.get(name)
        if c is None:
            problems.append(f"{name}: не запущен")
        elif c.get("State") != "running" or c.get("Health") not in ("healthy", ""):
            problems.append(f"{name}: {c.get('State')}/{c.get('Health') or '—'}")
    for name in ONE_SHOT:
        c = by_service.get(name)
        if c is None:
            problems.append(f"{name}: не запускался")
        elif c.get("State") == "exited" and int(c.get("ExitCode", 1)) != 0:
            raise RuntimeError(f"{name} завершился с кодом {c.get('ExitCode')}: docker compose logs {name}")
        elif c.get("State") != "exited":
            problems.append(f"{name}: выполняется")
    return problems


# Свежая телеметрия: отметка времени после начала ожидания; запас — на расхождение часов
FRESH_MARGIN_S = 5.0


def rfc3339(epoch_s: float) -> str:
    """Время UNIX → RFC 3339 UTC для range(start:) Flux."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_s))


def telemetry_flux(bucket: str, since_epoch_s: float) -> str:
    """Число точек LT101/level с момента since (данные прошлого запуска в томе не считаются)."""
    return (
        f'from(bucket: "{bucket}") |> range(start: {rfc3339(since_epoch_s)})'
        ' |> filter(fn: (r) => r._measurement == "telemetry" and r._field == "value")'
        ' |> filter(fn: (r) => r.device == "LT101" and r.metric == "level") |> count()'
    )


def birth_flux(bucket: str) -> str:
    """Последнее состояние узла PLC1 — online (1) или нет (0)."""
    return (
        f'from(bucket: "{bucket}") |> range(start: -1h)'
        ' |> filter(fn: (r) => r._measurement == "node_status" and r._field == "state" and r.device == "PLC1")'
        ' |> last() |> filter(fn: (r) => r._value == "online") |> count()'
    )


def count_from_csv(text: str) -> int:
    """Сумма целых _value в annotated CSV (результат count() по всем таблицам ответа)."""
    total = 0
    lines = (line for line in io.StringIO(text) if line.strip() and not line.startswith("#"))
    for row in csv.DictReader(lines):
        value = (row.get("_value") or "").strip()
        if value.isdigit():
            total += int(value)
    return total


def influx_count(files: Sequence[str], flux: str) -> int:
    """Результат запроса Flux с count() через influx CLI внутри контейнера influxdb."""
    res = run([*compose_cmd(files), "exec", "-T", "influxdb", "influx", "query", "--raw", flux])
    return count_from_csv(res.stdout) if res.returncode == 0 else 0


def grafana_dashboards(env: dict[str, str]) -> set[str]:
    port = env.get("GRAFANA_PORT", "3000")
    user = env.get("GRAFANA_ADMIN_USER", "admin")
    password = env.get("GRAFANA_ADMIN_PASSWORD", "")
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/search?tag=kns1")
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            items = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return set()
    return {item.get("uid", "") for item in items if isinstance(item, dict)}


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ожидание готовности стенда КНС-1")
    ap.add_argument("--compose-file", action="append", default=[], help="файл compose (можно несколько)")
    ap.add_argument("--data", action="store_true", help="ждать и данные в InfluxDB и Grafana")
    ap.add_argument("--emulator", action="store_true", help="ждать и сервис emulator")
    ap.add_argument("--timeout", type=float, default=300.0, help="предел ожидания, с")
    args = ap.parse_args(argv)

    env_path = ROOT / ".env"
    env = parse_keys(env_path.read_text(encoding="utf-8")) if env_path.exists() else {}
    bucket = env.get("INFLUX_BUCKET", "kns_raw")
    services = [*LONG_RUNNING, *(["emulator"] if args.emulator else [])]
    deadline = time.monotonic() + args.timeout
    started = time.monotonic()
    last = ""

    def report(state: str) -> None:
        nonlocal last
        if state != last:
            print(f"[{time.monotonic() - started:5.0f} с] {state}", flush=True)
            last = state

    while True:
        try:
            problems = health_problems(compose_ps(args.compose_file), services)
        except RuntimeError as exc:
            print(f"ошибка: {exc}", file=sys.stderr)
            return 1
        if not problems:
            break
        report("ждём сервисы: " + "; ".join(problems))
        if time.monotonic() > deadline:
            print("не дождались готовности сервисов: docker compose ps, docker compose logs", file=sys.stderr)
            return 1
        time.sleep(3)
    report("сервисы здоровы")
    if not args.data:
        return 0

    telemetry = telemetry_flux(bucket, time.time() - FRESH_MARGIN_S)
    birth = birth_flux(bucket)
    while True:
        points = influx_count(args.compose_file, telemetry)
        online = influx_count(args.compose_file, birth)
        boards = grafana_dashboards(env)
        missing = [uid for uid in DASHBOARD_UIDS if uid not in boards]
        if points > 0 and online > 0 and not missing:
            break
        report(
            f"ждём данные: свежих точек LT101/level — {points}, PLC1 online — {'да' if online else 'нет'},"
            f" дашбордов нет — {', '.join(missing) or '0'}"
        )
        if time.monotonic() > deadline:
            print("данные не появились: docker compose logs emulator telegraf", file=sys.stderr)
            return 1
        time.sleep(5)
    port = env.get("GRAFANA_PORT", "3000")
    report(f"данные на дашбордах: http://localhost:{port}/d/kns1-overview (логин — GRAFANA_ADMIN_* в .env)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
