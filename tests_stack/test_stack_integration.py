"""Сквозной путь на поднятом стенде: эмулятор (или ПЛК) → брокер → Telegraf → InfluxDB → запрос.

Стенд — любой из двух:
- docker compose: ``make demo DEV=1`` (порт InfluxDB на 127.0.0.1) или ``make demo`` (запросы — influx CLI
  внутри контейнера influxdb);
- локальный без Docker: ``tools_project/local_stack.ps1 start -Emulator``.

Тесты помечены ``integration`` и ``stack`` и пропускаются, если стенд не поднят (нет .env, брокера или
InfluxDB). С ``IIOT_STACK=1`` (``make test-stack``, CI) неподнятый стенд — ошибка, а не пропуск.
Пароли и токен — из .env. Пробные точки пишутся от имени устройства TEST1, которого нет в каталоге
(дашборды его не показывают), и удаляются в конце.

Проверки:
- эмулятор: все метрики каталога (раздел 3.4 docs/data_schema.md) доходят до InfluxDB по MQTT с тегами
  топика; тот же уровень LT101 и каждый узел OPC UA каталога (символы флагмана, станция KNS1 и LIC101) —
  и по OPC UA (вход opcua Telegraf), K1/general_alarm по обоим путям одинаков; узел PLC1 — online;
- пробная телеметрия по схеме доходит до measurement telemetry, другой мажорной версии — отбрасывается;
- публикация телеметрии от пользователя-оператора отклоняется брокером (ACL);
- обрыв связи узла: завещание (LWT) брокера — последнее состояние узла в базе offline;
- команда попадает в журнал аудита (measurement command);
- команда вне белого списка отклоняется (not_whitelisted) — ответ cmd_ack по MQTT, запись ответа в
  InfluxDB, счётчик PLC1/cmd_rejected вырос, режим устройства не изменился;
- значение вне диапазона — out_of_range; разрешённая команда устройства и команда станции — accepted;
- задача прореживания kns_downsample_1h (её текст как разовый запрос): mean — среднее, взвешенное по
  времени, min и max — по действовавшим значениям; сверка с расчётом по сырым точкам.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.parse
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest

import stack_catalog as sc
from local_stack import Influx, StackError, influx_healthy, load_env
from stack_wait import compose_cmd, count_from_csv

pytestmark = [pytest.mark.integration, pytest.mark.stack]

PROBE = "TEST1"
FILES = [f for f in os.environ.get("IIOT_COMPOSE_FILES", "docker-compose.yml").split(",") if f]
REQUIRED = os.environ.get("IIOT_STACK") == "1"


def unavailable(reason: str) -> None:
    if REQUIRED:
        pytest.fail(f"стенд не поднят (IIOT_STACK=1): {reason}")
    pytest.skip(f"стенд не поднят: {reason}")


class Db:
    """Запросы Flux: HTTP API InfluxDB на хосте или influx CLI в контейнере (порт не опубликован)."""

    def __init__(self, env: dict[str, str]) -> None:
        self.env = env
        self.org = env.get("INFLUX_ORG", "vodokanal")
        self.bucket = env.get("INFLUX_BUCKET", "kns_raw")
        self.url = os.environ.get("IIOT_INFLUX_URL") or f"http://127.0.0.1:{env.get('INFLUX_PORT', '8086')}"
        self.http = Influx(self.url, env.get("INFLUX_ADMIN_TOKEN", "")) if influx_healthy(self.url) else None

    @property
    def available(self) -> bool:
        if self.http is not None:
            return True
        if not shutil.which("docker"):
            return False
        return self._compose(["influx", "ping"]).returncode == 0

    def _compose(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*compose_cmd(FILES), "exec", "-T", "influxdb", *args],
            cwd=sc.REPO,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )

    def query(self, flux: str) -> str:
        if self.http is not None:
            return self.http.query(self.org, flux)
        res = self._compose(["influx", "query", "--raw", flux])
        assert res.returncode == 0, res.stderr
        return res.stdout

    def count(self, flux: str) -> int:
        return count_from_csv(self.query(flux))

    def rows(self, flux: str) -> list[dict[str, str]]:
        """Строки annotated CSV (все таблицы ответа)."""
        out: list[dict[str, str]] = []
        header: list[str] | None = None
        for line in self.query(flux).splitlines():
            if not line.strip():
                header = None
                continue
            if line.startswith("#"):
                continue
            cells = line.split(",")
            if header is None:
                header = cells
                continue
            out.append(dict(zip(header, cells, strict=False)))
        return out

    def delete_device(self, device: str) -> None:
        stop = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 3600))
        predicate = f'device="{device}"'
        if self.http is not None:
            query = urllib.parse.urlencode({"org": self.org, "bucket": self.bucket})
            self.http.request(
                "POST",
                f"/api/v2/delete?{query}",
                {"start": "1970-01-01T00:00:00Z", "stop": stop, "predicate": predicate},
            )
            return
        args = ["influx", "delete", "--bucket", self.bucket, "--start", "1970-01-01T00:00:00Z", "--stop", stop]
        self._compose([*args, "--predicate", predicate])


@pytest.fixture(scope="module")
def env() -> dict[str, str]:
    try:
        values = load_env()
    except StackError as exc:
        unavailable(str(exc))
        raise
    port = int(values.get("MQTT_PORT", "1883"))
    try:
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
    except OSError:
        unavailable(f"брокер MQTT не слушает 127.0.0.1:{port}")
    return values


@pytest.fixture(scope="module")
def db(env: dict[str, str]) -> Iterator[Db]:
    d = Db(env)
    if not d.available:
        unavailable(f"InfluxDB недоступна: ни {d.url}, ни docker compose exec influxdb")
    yield d
    with contextlib.suppress(StackError, AssertionError, OSError):
        d.delete_device(PROBE)


@pytest.fixture(scope="module")
def plc_online(db: Db) -> str:
    """Источник узла PLC1 (emulator или codesys); пропуск, если узел не в сети."""
    rows = db.rows(
        f'from(bucket: "{db.bucket}") |> range(start: -30d)'
        ' |> filter(fn: (r) => r._measurement == "node_status" and r.device == "PLC1")'
        ' |> filter(fn: (r) => r._field == "state" or r._field == "source")'
        ' |> last() |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")'
    )
    if not rows or rows[-1].get("state") != "online":
        unavailable("узел PLC1 не в сети: эмулятор (make demo, local_stack.ps1 start -Emulator) или ПЛК")
    return rows[-1].get("source", "")


def prefix() -> str:
    st = sc.station()
    return f"{st['site']}/{st['area']}/{st['unit']}"


def mqtt_client(env: dict[str, str], role: str) -> Any:
    mqtt = pytest.importorskip("paho.mqtt.client")
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=f"tests-stack-{role.lower()}-{uuid.uuid4().hex[:6]}"
    )
    client.username_pw_set(env[f"MQTT_{role}_USER"], env[f"MQTT_{role}_PASSWORD"])
    client.connect("127.0.0.1", int(env.get("MQTT_PORT", "1883")), keepalive=30)
    client.loop_start()
    return client


def publish(client: Any, topic: str, payload: dict[str, Any], retain: bool = False) -> None:
    info = client.publish(topic, json.dumps(payload), qos=1, retain=retain)
    info.wait_for_publish(timeout=10)


def wait_until(probe: Callable[[], int], timeout: float = 30.0) -> int:
    deadline = time.monotonic() + timeout
    while True:
        n = probe()
        if n or time.monotonic() > deadline:
            return n
        time.sleep(2)


def now_ms() -> int:
    return int(time.time() * 1000)


def command(name: str, cmd_id: str, value: float | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": "1.0",
        "cmd_id": cmd_id,
        "ts": now_ms(),
        "origin": "tests@stack",
        "command": name,
    }
    if value is not None:
        body["value"] = value
    return body


def send_command(env: dict[str, str], device: str, name: str, value: float | None = None) -> dict[str, Any]:
    """Команда от оператора и ответ cmd_ack узла (ждём до 15 с)."""
    cmd_id = uuid.uuid4().hex
    acks: list[dict[str, Any]] = []
    got = threading.Event()
    client = mqtt_client(env, "OPERATOR")

    def on_message(_c: Any, _u: Any, msg: Any) -> None:
        payload = json.loads(msg.payload)
        if payload.get("cmd_id") == cmd_id:
            acks.append(payload)
            got.set()

    client.on_message = on_message
    try:
        client.subscribe(f"{prefix()}/{device}/cmd_ack/{name}", qos=1)
        time.sleep(1)
        publish(client, f"{prefix()}/{device}/cmd/{name}", command(name, cmd_id, value))
        assert got.wait(15), f"нет ответа cmd_ack на {device}/{name}"
    finally:
        client.loop_stop()
        client.disconnect()
    return acks[0]


def last_value(db: Db, device: str, metric: str) -> float | None:
    rows = db.rows(
        f'from(bucket: "{db.bucket}") |> range(start: -1h)'
        f' |> filter(fn: (r) => r._measurement == "telemetry" and r._field == "value" and r.source == "mqtt")'
        f' |> filter(fn: (r) => r.device == "{device}" and r.metric == "{metric}") |> last()'
    )
    return float(rows[-1]["_value"]) if rows else None


# --- эмулятор → брокер → InfluxDB ---------------------------------------------------------------------
def test_all_catalog_metrics_reach_influxdb(db: Db, plc_online: str) -> None:
    """Каждая метрика каталога за последние 3 контрольных периода есть в базе (путь MQTT)."""
    rows = db.rows(
        f'from(bucket: "{db.bucket}") |> range(start: -3m)'
        ' |> filter(fn: (r) => r._measurement == "telemetry" and r._field == "value" and r.source == "mqtt")'
        ' |> filter(fn: (r) => r.site == "vodokanal" and r.area == "kns1" and r.unit == "station")'
        ' |> last() |> group() |> keep(columns: ["device", "metric", "_value"])'
    )
    seen = {(r["device"], r["metric"]) for r in rows}
    expected = {(m.device, m.metric) for m in sc.load_catalog()}
    assert expected <= seen, f"нет в InfluxDB: {sorted(expected - seen)}"
    level = next(float(r["_value"]) for r in rows if (r["device"], r["metric"]) == ("LT101", "level"))
    assert 0.0 <= level <= 5.0


def test_opcua_path_reaches_influxdb(db: Db, plc_online: str) -> None:
    """Тот же уровень LT101 Telegraf читает с OPC UA-сервера (source = opcua, поле opcua_status)."""
    flux = (
        f'from(bucket: "{db.bucket}") |> range(start: -2m)'
        ' |> filter(fn: (r) => r._measurement == "telemetry" and r.source == "opcua")'
        ' |> filter(fn: (r) => r.device == "LT101" and r.metric == "level" and r._field == "value") |> count()'
    )
    assert wait_until(lambda: db.count(flux), timeout=30) > 0


def test_opcua_path_covers_catalog_nodes(db: Db, plc_online: str) -> None:
    """Каждый узел OPC UA каталога (символы флагмана, в том числе станция KNS1 и LIC101) доходит до базы;
    K1/general_alarm по OPC UA (xK1 через инверсию Starlark) совпадает с путём MQTT."""
    expected = {(m.device, m.metric) for m in sc.load_catalog() if m.plc_path}

    def seen() -> set[tuple[str, str]]:
        rows = db.rows(
            f'from(bucket: "{db.bucket}") |> range(start: -2m)'
            ' |> filter(fn: (r) => r._measurement == "telemetry" and r._field == "value" and r.source == "opcua")'
            ' |> last() |> group() |> keep(columns: ["device", "metric", "_value"])'
        )
        return {(r["device"], r["metric"]) for r in rows}

    wait_until(lambda: expected <= seen(), timeout=40)
    missing = expected - seen()
    assert not missing, f"нет по OPC UA: {sorted(missing)}"
    rows = db.rows(
        f'from(bucket: "{db.bucket}") |> range(start: -2m)'
        ' |> filter(fn: (r) => r._measurement == "telemetry" and r._field == "value")'
        ' |> filter(fn: (r) => r.device == "K1" and r.metric == "general_alarm") |> last()'
        ' |> group() |> keep(columns: ["source", "_value"])'
    )
    by_source = {r["source"]: float(r["_value"]) for r in rows}
    assert set(by_source) == {"mqtt", "opcua"} and by_source["mqtt"] == by_source["opcua"], by_source


def test_node_birth_recorded(db: Db, plc_online: str) -> None:
    assert plc_online in ("emulator", "codesys")


# --- пробная телеметрия, версия схемы, ACL, аудит команд ---------------------------------------------
def test_telemetry_reaches_influxdb(env: dict[str, str], db: Db) -> None:
    value = round(time.time() % 1000, 3)
    client = mqtt_client(env, "PLC")
    try:
        publish(
            client,
            f"{prefix()}/{PROBE}/probe",
            {"schema_version": "1.0", "ts": now_ms(), "value": value, "quality": "good"},
        )
    finally:
        client.loop_stop()
        client.disconnect()
    flux = (
        f'from(bucket: "{db.bucket}") |> range(start: -5m)'
        f' |> filter(fn: (r) => r._measurement == "telemetry" and r.device == "{PROBE}" and r.metric == "probe")'
        f' |> filter(fn: (r) => r._field == "value" and r._value == {value} and r.source == "mqtt")'
        ' |> filter(fn: (r) => r.site == "vodokanal" and r.area == "kns1" and r.unit == "station") |> count()'
    )
    assert wait_until(lambda: db.count(flux)) == 1


def test_other_schema_major_is_dropped(env: dict[str, str], db: Db) -> None:
    client = mqtt_client(env, "PLC")
    try:
        publish(
            client,
            f"{prefix()}/{PROBE}/probe_v2",
            {"schema_version": "2.0", "ts": now_ms(), "value": 1.0, "quality": "good"},
        )
    finally:
        client.loop_stop()
        client.disconnect()
    time.sleep(10)
    flux = (
        f'from(bucket: "{db.bucket}") |> range(start: -5m)'
        ' |> filter(fn: (r) => r._measurement == "telemetry" and r.metric == "probe_v2") |> count()'
    )
    assert db.count(flux) == 0


def test_operator_cannot_publish_telemetry(env: dict[str, str], db: Db) -> None:
    client = mqtt_client(env, "OPERATOR")
    try:
        publish(
            client,
            f"{prefix()}/{PROBE}/probe_acl",
            {"schema_version": "1.0", "ts": now_ms(), "value": 1.0, "quality": "good"},
        )
    finally:
        client.loop_stop()
        client.disconnect()
    time.sleep(10)
    flux = (
        f'from(bucket: "{db.bucket}") |> range(start: -5m)'
        ' |> filter(fn: (r) => r._measurement == "telemetry" and r.metric == "probe_acl") |> count()'
    )
    assert db.count(flux) == 0


def test_command_is_audited(env: dict[str, str], db: Db) -> None:
    cmd_id = uuid.uuid4().hex
    client = mqtt_client(env, "OPERATOR")
    try:
        publish(client, f"{prefix()}/{PROBE}/cmd/Ack", command("Ack", cmd_id))
    finally:
        client.loop_stop()
        client.disconnect()
    flux = (
        f'from(bucket: "{db.bucket}") |> range(start: -5m)'
        f' |> filter(fn: (r) => r._measurement == "command" and r.device == "{PROBE}" and r.command == "Ack")'
        f' |> filter(fn: (r) => r._field == "cmd_id" and r._value == "{cmd_id}") |> count()'
    )
    assert wait_until(lambda: db.count(flux)) == 1


def test_lwt_marks_node_offline(env: dict[str, str], db: Db) -> None:
    """Обрыв связи узла: брокер публикует завещание, последнее состояние узла в базе — offline.

    ts завещания — время подключения (раньше рождения), поэтому порядок в базе держится на времени
    приёма Telegraf для node_status (telegraf.conf, data_schema.md, 7.1).
    """
    mqtt = pytest.importorskip("paho.mqtt.client")
    topic = f"{prefix()}/{PROBE}/status/connection"
    connect_ts = now_ms()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"tests-stack-lwt-{uuid.uuid4().hex[:6]}")
    client.username_pw_set(env["MQTT_PLC_USER"], env["MQTT_PLC_PASSWORD"])
    lwt = {"schema_version": "1.0", "ts": connect_ts, "node": PROBE, "state": "offline", "reason": "lwt"}
    client.will_set(topic, json.dumps(lwt), qos=1, retain=False)
    client.connect("127.0.0.1", int(env.get("MQTT_PORT", "1883")), keepalive=10)
    client.loop_start()
    birth = {"schema_version": "1.0", "ts": now_ms(), "node": PROBE, "state": "online", "reason": "birth"}
    publish(client, topic, birth)
    time.sleep(2)
    client.loop_stop()
    sock = client.socket()
    assert sock is not None
    sock.close()  # обрыв без DISCONNECT — брокер обязан опубликовать завещание

    def last_state() -> str:
        rows = db.rows(
            f'from(bucket: "{db.bucket}") |> range(start: -5m)'
            f' |> filter(fn: (r) => r._measurement == "node_status" and r.device == "{PROBE}" and r._field == "state")'
            " |> last()"
        )
        return rows[-1]["_value"] if rows else ""

    assert wait_until(lambda: int(last_state() == "offline"), timeout=40) == 1, last_state()


# --- команды: белый список и диапазоны, сквозь брокер и базу -----------------------------------------
def test_non_whitelisted_command_rejected_end_to_end(env: dict[str, str], db: Db, plc_online: str) -> None:
    """SetOos (вывод из работы) по MQTT запрещён: отказ, ответ в журнале, режим насоса не меняется."""
    rejected_before = last_value(db, "PLC1", "cmd_rejected") or 0.0
    ack = send_command(env, "P101", "SetOos")
    assert ack["result"] == "rejected" and ack["reason"] == "not_whitelisted", ack
    assert "cmd_result" not in ack  # до устройства команда не дошла
    flux = (
        f'from(bucket: "{db.bucket}") |> range(start: -5m)'
        ' |> filter(fn: (r) => r._measurement == "command_ack" and r.device == "P101" and r.command == "SetOos")'
        ' |> filter(fn: (r) => r._field == "cmd_id" or r._field == "reason")'
        ' |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")'
        f' |> filter(fn: (r) => r.cmd_id == "{ack["cmd_id"]}") |> group() |> keep(columns: ["reason"])'
    )
    assert wait_until(lambda: len(db.rows(flux))) == 1, "ответ на команду не записан в InfluxDB"
    assert db.rows(flux)[0]["reason"] == "not_whitelisted"
    # счётчик отказов узла (метрика PLC1/cmd_rejected) публикуется по изменению
    assert wait_until(lambda: int((last_value(db, "PLC1", "cmd_rejected") or 0.0) > rejected_before)) == 1
    time.sleep(3)
    assert last_value(db, "P101", "mode") != 4.0, "насос выведен из работы командой вне белого списка"


def test_out_of_range_value_rejected(env: dict[str, str], db: Db, plc_online: str) -> None:
    ack = send_command(env, "P101", "SpeedSp", 150.0)
    assert ack["result"] == "rejected" and ack["reason"] == "out_of_range", ack


def test_whitelisted_command_accepted(env: dict[str, str], db: Db, plc_online: str) -> None:
    ack = send_command(env, "LT101", "Ack")
    assert ack["result"] == "accepted" and ack["reason"] == "ok", ack
    assert ack.get("cmd_result", "Accepted") == "Accepted"


def test_station_command_accepted(env: dict[str, str], db: Db, plc_online: str) -> None:
    """Команда станции (GVL_Station.stStationCmd флагмана): способ уже «ПИД уровня» — состояние не меняется."""
    ack = send_command(env, "KNS1", "SetLevelPid")
    assert ack["result"] == "accepted" and ack["reason"] == "ok", ack
    assert ack.get("cmd_result", "Accepted") == "Accepted"


# --- прореживание (задача kns_downsample_1h) -------------------------------------------------------------
def downsample_adhoc(bucket: str, stop_s: int, every: str, device: str, metric: str) -> str:
    """Текст задачи как разовый запрос: своё «сейчас» и окно, yield вместо to(), один ряд."""
    flux = (sc.REPO / "influxdb" / "tasks" / "downsample_1h.flux").read_text(encoding="utf-8")
    stop = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stop_s))
    head = 'option task = {name: "kns_downsample_1h", every: 1h, offset: 2m}'
    assert head in flux
    flux = flux.replace(head, f"option now = () => {stop}\ntask = {{every: {every}}}")
    flux = flux.replace("@RAW_BUCKET@", bucket)
    flux = flux.replace(
        "        |> pivot(",
        f'        |> filter(fn: (r) => r.device == "{device}" and r.metric == "{metric}")\n        |> pivot(',
        1,
    )
    for name in ("mean", "min", "max"):
        flux = flux.replace('|> to(bucket: "@AGG_BUCKET@")', f'|> yield(name: "{name}")', 1)
    assert "|> to(" not in flux
    return flux


def held_lt101(db: Db, start_s: int, stop_s: int, hold_s: int) -> tuple[float, float, list[float]]:
    """Сырые точки LT101/level (MQTT, без bad) → взвешенная сумма, суммарный вес (с) и действовавшие значения."""
    since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_s - hold_s))
    stop = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stop_s))
    raw = db.rows(
        f'from(bucket: "{db.bucket}") |> range(start: {since}, stop: {stop})'
        ' |> filter(fn: (r) => r._measurement == "telemetry" and r.source == "mqtt")'
        ' |> filter(fn: (r) => r.device == "LT101" and r.metric == "level")'
        ' |> filter(fn: (r) => r._field == "value" or r._field == "quality")'
        ' |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")'
        " |> map(fn: (r) => ({r with t: uint(v: r._time)}))"
    )
    points = sorted((int(r["t"]) / 1e9, float(r["value"])) for r in raw if r.get("value") and r.get("quality") != "bad")
    wsum = weight = 0.0
    held = []
    for i, (t, v) in enumerate(points):
        end = min(t + hold_s, points[i + 1][0] if i + 1 < len(points) else stop_s, stop_s)
        w = max(0.0, end - max(t, start_s))
        if w > 0:
            wsum += v * w
            weight += w
            held.append(v)
    return wsum, weight, held


def test_downsample_mean_is_time_weighted(db: Db, plc_online: str) -> None:
    """mean агрегата — среднее, взвешенное по времени (удержание до 10 мин, без quality = bad), как в отчёте.

    Окно — 10 минут, закончившиеся 15 с назад (запись Telegraf — раз в 5 с): ожидаемое значение
    считается здесь же по сырым точкам. Сразу после make demo точек в окне может ещё не быть — ждём.
    """
    hold_s = 600
    deadline = time.monotonic() + 90
    while True:
        stop_s = int(time.time()) - 15
        start_s = stop_s - 600
        wsum, weight, held = held_lt101(db, start_s, stop_s, hold_s)
        if weight > 0 or time.monotonic() > deadline:
            break
        time.sleep(5)
    assert weight > 0, "нет точек LT101/level за окно"
    got = {
        r["_field"]: float(r["_value"])
        for r in db.rows(downsample_adhoc(db.bucket, stop_s, "10m", "LT101", "level"))
        if r.get("source") == "mqtt" and r.get("_field") in ("mean", "min", "max")
    }
    assert set(got) == {"mean", "min", "max"}, got
    assert got["mean"] == pytest.approx(wsum / weight, abs=1e-6)
    assert got["min"] == pytest.approx(min(held)) and got["max"] == pytest.approx(max(held))
