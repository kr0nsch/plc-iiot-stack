"""Локальный стенд без Docker: те же конфигурации, что у docker compose, на родных сборках Windows.

Назначение: шаги для ``tools_project/local_stack.ps1`` (install, start, stop, status) — запуск стенда
на компьютере без Docker и без прав администратора: InfluxDB 2, Telegraf и Grafana — официальные
сборки для Windows (zip), брокер MQTT — amqtt (Python, свой venv), эмулятор — ``emulator/``.
Автор: kr0nsch. Версия: 1.0. Отличия от docker compose — docs/ARCHITECTURE.md, раздел
«Локальный стенд без Docker».

Принцип: стенд не настраивается заново. Окружение сервиса берётся из ``docker-compose.yml`` с
подстановкой ``.env`` по правилам compose и переводится на хост:

- адреса сервисов compose (``mosquitto:1883``, ``influxdb:8086``, ``emulator:4840``) — в
  ``127.0.0.1`` и локальные порты (OPC UA эмулятора — 4841: порт 4840 обычно занят OPC UA-сервером
  рантайма CODESYS Control Win);
- пути внутри контейнеров — в пути на хосте по томам сервиса: ``./grafana/dashboards`` — каталог
  репозитория, именованный том (``influx-tokens``) — ``build/local-stack/volumes/<том>``.

Что так не переносится (брокер amqtt вместо Mosquitto, провиженинг Grafana с путями хоста,
первичная установка InfluxDB через HTTP API вместо скрипта образа), собрано здесь же и описано в
docs/ARCHITECTURE.md.

Подкоманды:
  install               скачать сборки (SHA-256 сверяется) и создать venv amqtt
  spec NAME             JSON для запуска сервиса: exe, args, env, cwd (читает local_stack.ps1)
  broker-config         файл паролей и конфигурация amqtt из .env и mosquitto/config/acl.template
                        (запускается интерпретатором из venv amqtt: нужен pwdlib с argon2)
  influx-init           первичная установка InfluxDB и то же, что influxdb/influxdb-init.sh (HTTP API)
  grafana-provisioning  копия grafana/provisioning с путями и адресом InfluxDB хоста
  wait NAME             ждать готовности сервиса
  wait-data             ждать данных: телеметрия в InfluxDB, рождение PLC1, три дашборда в Grafana
  status                процессы, порты и проверки здоровья
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from make_env import parse_keys
from stack_wait import DASHBOARD_UIDS, FRESH_MARGIN_S, birth_flux, count_from_csv, telemetry_flux

ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = ROOT / "docker-compose.yml"
DEFAULT_STATE = ROOT / "build" / "local-stack"
DEFAULT_TOOLS = Path.home() / ".local" / "plc-tools" / "iiot"
SERVICES = ("broker", "influxdb", "telegraf", "grafana", "emulator")
# Сервис локального стенда → сервис docker-compose.yml, чьё окружение и тома он повторяет
COMPOSE_SERVICE = {
    "broker": "mosquitto",
    "influxdb": "influxdb",
    "telegraf": "telegraf",
    "grafana": "grafana",
    "emulator": "emulator",
}
AMQTT_VERSION = "0.12.1"
# Каталог сертификата клиента OPC UA в контейнере Telegraf (том telegraf-pki, telegraf/docker-entrypoint.sh)
TELEGRAF_PKI_DIR = "/var/lib/telegraf/pki"
# База часовых поясов для influxd (см. zoneinfo_zip)
TZDATA_VERSION = "2026.5"
# Признак Windows — не через sys.platform: mypy сужает его по платформе проверки
WINDOWS = os.name == "nt"


@dataclass(frozen=True)
class Component:
    """Официальная сборка для Windows: версия совпадает с образом в docker-compose.yml."""

    name: str
    version: str
    url: str
    sha256: str
    image: str  # образ compose той же версии (сверяет tests_stack/test_local_stack.py)


# SHA-256 — из заметок к релизам (GitHub influxdata/influxdb v2.9.1, influxdata/telegraf v1.39.3) и
# файла .sha256 рядом с архивом Grafana на dl.grafana.com
COMPONENTS = (
    Component(
        "influxdb",
        "2.9.1",
        "https://dl.influxdata.com/influxdb/releases/influxdb2-2.9.1-windows_amd64.zip",
        "d8b93916a5e21fe348dfdb8de7ea04fb7425b38939486e874cd8096463b91043",
        "influxdb:2.9.1-alpine",
    ),
    Component(
        "telegraf",
        "1.39.3",
        "https://dl.influxdata.com/telegraf/releases/telegraf-1.39.3_windows_amd64.zip",
        "61d03076a17981596604fd3d3f32a4939c24e131cff7099b9a31de0efd3afc53",
        "telegraf:1.39.3-alpine",
    ),
    Component(
        "grafana",
        "12.4.12",
        "https://dl.grafana.com/oss/release/grafana-12.4.12.windows-amd64.zip",
        "7e7c979015240f188a122400421cfe0c33d3ba5fc46d899376bb78bff2d65b31",
        "grafana/grafana:12.4.12",
    ),
)


class StackError(RuntimeError):
    """Ошибка подготовки или запуска локального стенда (сообщение — для человека)."""


# --- окружение и compose -----------------------------------------------------------------------------
def unquote(value: str) -> str:
    """Значение .env без внешних кавычек (как читает compose)."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def load_env(path: Path | None = None, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Значения ``.env``; переменная окружения процесса с тем же именем важнее файла, как у docker compose.

    Так секрет, которого не должно быть в ``.env`` (например, вход OPC UA пользователя рантайма CODESYS),
    передаётся только окружению запуска.
    """
    path = path or ROOT / ".env"
    if not path.exists():
        raise StackError(f"нет {path}: выполните python tools_project/make_env.py (make env)")
    shell = os.environ if environ is None else environ
    return {k: shell.get(k, unquote(v)) for k, v in parse_keys(path.read_text(encoding="utf-8")).items()}


_VAR_RE = re.compile(r"\$\$|\$\{([A-Za-z_][A-Za-z0-9_]*)(?:(:?[-?])([^}]*))?\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def interpolate(text: str, env: Mapping[str, str]) -> str:
    """Подстановка переменных по правилам docker compose: ``${X}``, ``${X:-d}``, ``${X-d}``, ``${X:?e}``, ``$$``."""

    def repl(m: re.Match[str]) -> str:
        if m.group(0) == "$$":
            return "$"
        name = m.group(1) or m.group(4)
        op, arg = m.group(2), m.group(3) or ""
        value = env.get(name)
        if op == ":-":
            return value if value else arg
        if op == "-":
            return value if value is not None else arg
        if op in (":?", "?") and (value is None or (op == ":?" and value == "")):
            raise StackError(f"{name}: {arg}")
        return value or ""

    return _VAR_RE.sub(repl, text)


def compose_services() -> dict[str, Any]:
    data = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    services: dict[str, Any] = data["services"]
    return services


def compose_environment(service: str, env: Mapping[str, str]) -> dict[str, str]:
    raw = compose_services()[service].get("environment") or {}
    if isinstance(raw, list):
        raw = dict(item.split("=", 1) for item in raw)
    return {str(k): interpolate(str(v), env) for k, v in raw.items()}


@dataclass(frozen=True)
class Layout:
    """Где лежат сборки, состояние стенда и какие порты слушают сервисы на хосте."""

    state: Path
    tools: Path
    mqtt_port: int
    influx_port: int
    grafana_port: int
    opcua_port: int
    telegraf_health_port: int

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Layout:
        def port(key: str, default: int) -> int:
            return int(os.environ.get(key) or env.get(key) or default)

        return cls(
            state=Path(os.environ.get("LOCAL_STACK_STATE") or DEFAULT_STATE),
            tools=Path(os.environ.get("IIOT_TOOLS_DIR") or DEFAULT_TOOLS),
            mqtt_port=port("MQTT_PORT", 1883),
            influx_port=port("INFLUX_PORT", 8086),
            grafana_port=port("GRAFANA_PORT", 3000),
            opcua_port=port("LOCAL_OPCUA_PORT", 4841),
            telegraf_health_port=port("LOCAL_TELEGRAF_HEALTH_PORT", 8080),
        )

    @property
    def influx_url(self) -> str:
        return f"http://127.0.0.1:{self.influx_port}"

    @property
    def grafana_url(self) -> str:
        return f"http://127.0.0.1:{self.grafana_port}"

    def host_ports(self) -> dict[str, tuple[int, int]]:
        """Сервис compose → (порт в контейнере, порт на хосте)."""
        return {
            "mosquitto": (1883, self.mqtt_port),
            "influxdb": (8086, self.influx_port),
            "emulator": (4840, self.opcua_port),
            "grafana": (3000, self.grafana_port),
        }

    def rewrite_hosts(self, value: str) -> str:
        """``influxdb:8086`` → ``127.0.0.1:8086``; значение, равное имени сервиса, → ``127.0.0.1``."""
        ports = self.host_ports()
        if value in ports:
            return "127.0.0.1"
        for name, (inner, outer) in ports.items():
            value = value.replace(f"{name}:{inner}", f"127.0.0.1:{outer}")
        return value

    def map_path(self, service: str, container_path: str) -> Path:
        """Путь в контейнере сервиса → путь на хосте по его томам (bind-том или именованный том)."""
        best: tuple[str, Path] | None = None
        for vol in compose_services()[service].get("volumes") or []:
            parts = str(vol).split(":")
            source, target = parts[0], parts[1]
            if container_path == target or container_path.startswith(target.rstrip("/") + "/"):
                host = (ROOT / source).resolve() if source.startswith(".") else self.state / "volumes" / source
                if best is None or len(target) > len(best[0]):
                    best = (target, host)
        if best is None:
            raise StackError(f"{service}: путь {container_path} не смонтирован ни одним томом docker-compose.yml")
        target, host = best
        rest = container_path[len(target) :].lstrip("/")
        return host / rest if rest else host

    # --- сборки ---
    def find(self, pattern: str) -> Path:
        hits = sorted(self.tools.glob(pattern))
        if not hits:
            raise StackError(f"нет {self.tools / pattern}: powershell -File tools_project/local_stack.ps1 install")
        return hits[-1]

    @property
    def amqtt_python(self) -> Path:
        return self.tools / "amqtt" / "venv" / "Scripts" / "python.exe"


def posix(path: Path) -> str:
    return path.as_posix()


# --- спецификации запуска ----------------------------------------------------------------------------
def spec(name: str, env: Mapping[str, str], layout: Layout) -> dict[str, Any]:
    """Как запустить сервис: exe, args, env (добавляется к окружению процесса), cwd."""
    logs = layout.state / "logs"
    if name == "broker":
        exe = layout.tools / "amqtt" / "venv" / "Scripts" / "amqtt.exe"
        if not exe.exists():
            raise StackError(f"нет {exe}: powershell -File tools_project/local_stack.ps1 install")
        return {
            "exe": str(exe),
            "args": ["-c", str(layout.state / "amqtt" / "broker.yaml")],
            "env": {},
            "cwd": str(layout.state / "amqtt"),
        }
    if name == "influxdb":
        data = layout.map_path("influxdb", "/var/lib/influxdb2")
        out = {
            "INFLUXD_BOLT_PATH": str(data / "influxd.bolt"),
            "INFLUXD_ENGINE_PATH": str(data / "engine"),
            "INFLUXD_SQLITE_PATH": str(data / "influxd.sqlite"),
            "INFLUXD_HTTP_BIND_ADDRESS": f"127.0.0.1:{layout.influx_port}",
        }
        compose = compose_environment("influxdb", env)
        out["INFLUXD_REPORTING_DISABLED"] = compose.get("INFLUXD_REPORTING_DISABLED", "true")
        zoneinfo = layout.tools / "influxdb" / "zoneinfo.zip"
        if zoneinfo.exists():
            out["ZONEINFO"] = str(zoneinfo)
        return {"exe": str(layout.find("influxdb/**/influxd.exe")), "args": [], "env": out, "cwd": str(data)}
    if name == "telegraf":
        compose = {k: layout.rewrite_hosts(v) for k, v in compose_environment("telegraf", env).items()}
        token_file = layout.map_path("telegraf", compose.pop("INFLUX_TOKEN_FILE"))
        if not token_file.exists():
            raise StackError(f"нет токена Telegraf {token_file}: сначала influx-init")
        compose["INFLUX_TOKEN"] = token_file.read_text(encoding="utf-8").strip()
        # Пути и адреса, которые в контейнере заданы по умолчанию в telegraf.conf
        compose["TELEGRAF_LOOKUP_DIR"] = posix(layout.map_path("telegraf", "/etc/telegraf/lookup"))
        compose["TELEGRAF_HEALTH_ADDRESS"] = f"http://127.0.0.1:{layout.telegraf_health_port}"
        args = ["--config", str(layout.map_path("telegraf", "/etc/telegraf/telegraf.conf"))]
        # То же решение, что в telegraf/docker-entrypoint.sh
        if compose.get("OPCUA_ENABLED", "true").lower() in ("true", "1", "yes"):
            args += ["--config-directory", str(layout.map_path("telegraf", "/etc/telegraf/telegraf.d"))]
        # Сертификат клиента OPC UA — как в entrypoint: только с политикой не None, по умолчанию в томе
        # telegraf-pki (Telegraf создаёт его один раз)
        if compose.get("OPCUA_SECURITY_POLICY", "None") != "None":
            pki = layout.map_path("telegraf", TELEGRAF_PKI_DIR)
            compose["OPCUA_CERTIFICATE"] = compose.get("OPCUA_CERTIFICATE") or posix(pki / "cert.pem")
            compose["OPCUA_PRIVATE_KEY"] = compose.get("OPCUA_PRIVATE_KEY") or posix(pki / "key.pem")
        else:
            compose["OPCUA_CERTIFICATE"] = compose["OPCUA_PRIVATE_KEY"] = ""
        return {"exe": str(layout.find("telegraf/**/telegraf.exe")), "args": args, "env": compose, "cwd": str(logs)}
    if name == "grafana":
        exe = layout.find("grafana/*/bin/grafana.exe")
        compose = {k: layout.rewrite_hosts(v) for k, v in compose_environment("grafana", env).items()}
        home = compose.get("GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH")
        if home:
            compose["GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH"] = str(layout.map_path("grafana", home))
        data = layout.map_path("grafana", "/var/lib/grafana")
        compose.update(
            {
                "GF_PATHS_DATA": str(data),
                "GF_PATHS_LOGS": str(logs / "grafana"),
                "GF_PATHS_PLUGINS": str(data / "plugins"),
                "GF_PATHS_PROVISIONING": str(layout.state / "grafana" / "provisioning"),
                "GF_SERVER_HTTP_ADDR": env.get("GRAFANA_BIND", "127.0.0.1") or "127.0.0.1",
                "GF_SERVER_HTTP_PORT": str(layout.grafana_port),
            }
        )
        if os.environ.get("LOCAL_GRAFANA_ANONYMOUS") == "1":
            # Только для снимков дашбордов на 127.0.0.1: чтение без входа (в compose выключено)
            compose["GF_AUTH_ANONYMOUS_ENABLED"] = "true"
            compose["GF_AUTH_ANONYMOUS_ORG_ROLE"] = "Viewer"
        return {
            "exe": str(exe),
            "args": ["server", "--homepath", str(exe.parent.parent)],
            "env": compose,
            "cwd": str(exe.parent.parent),
            "dirs": [str(data), str(data / "plugins"), str(logs / "grafana")],
        }
    if name == "emulator":
        compose = {k: layout.rewrite_hosts(v) for k, v in compose_environment("emulator", env).items()}
        compose["EMU_OPCUA_ENDPOINT"] = f"opc.tcp://127.0.0.1:{layout.opcua_port}"
        compose["EMU_OPCUA_PKI_DIR"] = str(layout.state / "volumes" / "emulator-pki")
        compose["PYTHONUTF8"] = "1"
        return {
            "exe": sys.executable,
            "args": ["-m", "iiot_emulator", "run"],
            "env": compose,
            "cwd": str(ROOT / "emulator"),
        }
    raise StackError(f"неизвестный сервис {name}; есть: {', '.join(SERVICES)}")


# --- процессы -----------------------------------------------------------------------------------------
def pid_file(layout: Layout, name: str) -> Path:
    return layout.state / "pids" / f"{name}.pid"


def pid_alive(pid: int) -> bool:
    if WINDOWS:
        res = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=False
        )
        return f'"{pid}"' in res.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def running_pid(layout: Layout, name: str) -> int | None:
    path = pid_file(layout, name)
    if not path.exists():
        return None
    pid = int(path.read_text(encoding="utf-8").strip())
    if pid_alive(pid):
        return pid
    path.unlink()
    return None


def launch(name: str, env: Mapping[str, str], layout: Layout) -> int:
    """Запустить сервис отдельным процессом без консоли; вывод — в build/local-stack/logs/<имя>.log.

    Процесс не наследует дескрипторы запускающего (close_fds; на Windows — только стандартные
    потоки): иначе канал вывода PowerShell или CI оставался бы открытым, пока работает сервис.
    """
    pid = running_pid(layout, name)
    if pid is not None:
        return pid
    s = spec(name, env, layout)
    logs = layout.state / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    for d in [s["cwd"], *s.get("dirs", [])]:
        Path(d).mkdir(parents=True, exist_ok=True)
    child_env = {**os.environ, **s["env"]}
    child_env.pop("LOCAL_GRAFANA_ANONYMOUS", None)
    flags = 0
    if WINDOWS:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    with (logs / f"{name}.log").open("ab") as log:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log.write(f"=== {stamp} запуск {name}{os.linesep}".encode())
        log.flush()
        cmd = [s["exe"], *s["args"]]
        try:
            # вне задания (job) запускающей оболочки: сервис переживает её завершение
            proc = subprocess.Popen(
                cmd,
                cwd=s["cwd"],
                env=child_env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=flags | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0),
            )
        except PermissionError:
            proc = subprocess.Popen(
                cmd,
                cwd=s["cwd"],
                env=child_env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
    path = pid_file(layout, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


def stop(name: str, layout: Layout) -> int | None:
    """Остановить сервис вместе с дочерними процессами (amqtt.exe запускает python.exe)."""
    pid = running_pid(layout, name)
    if pid is None:
        return None
    if WINDOWS:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
    else:
        os.kill(pid, 15)
    pid_file(layout, name).unlink(missing_ok=True)
    return pid


# --- брокер amqtt -------------------------------------------------------------------------------------
ROLES = ("PLC", "TELEGRAF", "OPERATOR", "MONITOR")
NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def broker_users(env: Mapping[str, str]) -> dict[str, str]:
    """Пользователи брокера из .env с теми же проверками, что в mosquitto/docker-entrypoint.sh."""
    users: dict[str, str] = {}
    for role in ROLES:
        user = env.get(f"MQTT_{role}_USER", "")
        password = env.get(f"MQTT_{role}_PASSWORD", "")
        if not NAME_RE.match(user):
            raise StackError(f"MQTT_{role}_USER='{user}': допустимы латинские буквы, цифры, _ и -")
        if not password:
            raise StackError(f"не задан MQTT_{role}_PASSWORD (.env)")
        if password.startswith("change-me"):
            raise StackError(f"MQTT_{role}_PASSWORD не изменён: make env создаёт .env со случайными паролями")
        users[user] = password
    return users


def parse_acl(text: str) -> dict[str, dict[str, list[str]]]:
    """ACL Mosquitto (``user``, ``topic read|write|readwrite``) → {пользователь: {read, write}}."""
    acl: dict[str, dict[str, list[str]]] = {}
    current: dict[str, list[str]] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        words = line.split()
        if words[0] == "user" and len(words) == 2:
            current = acl.setdefault(words[1], {"read": [], "write": []})
        elif words[0] == "topic" and current is not None:
            access, topic = (words[1], words[2]) if len(words) == 3 else ("readwrite", words[1])
            if access in ("read", "readwrite"):
                current["read"].append(topic)
            if access in ("write", "readwrite"):
                current["write"].append(topic)
        else:
            raise StackError(f"ACL: строка не поддерживается локальным брокером: {line}")
    return acl


def render_acl(env: Mapping[str, str]) -> str:
    """Тот же текст, что собирает sed в mosquitto/docker-entrypoint.sh."""
    root = env.get("MQTT_TOPIC_ROOT") or "vodokanal"
    if not NAME_RE.match(root):
        raise StackError(f"MQTT_TOPIC_ROOT='{root}': допустимы латинские буквы, цифры, _ и -")
    text = (ROOT / "mosquitto" / "config" / "acl.template").read_text(encoding="utf-8").replace("@ROOT@", root)
    for role in ROLES:
        text = text.replace(f"@{role}_USER@", env.get(f"MQTT_{role}_USER", ""))
    return text


def amqtt_config(env: Mapping[str, str], layout: Layout, password_file: Path) -> dict[str, Any]:
    """Конфигурация amqtt: вход только по паролю, ACL на публикацию и подписку, темы $SYS."""
    acl = parse_acl(render_acl(env))
    bind = env.get("MQTT_BIND") or "127.0.0.1"
    return {
        "listeners": {"default": {"type": "tcp", "bind": f"{bind}:{layout.mqtt_port}"}},
        "plugins": {
            "amqtt.plugins.authentication.FileAuthPlugin": {"password_file": str(password_file)},
            "amqtt.plugins.topic_checking.TopicAccessControlListPlugin": {
                "publish_acl": {user: rules["write"] for user, rules in acl.items()},
                "acl": {user: rules["read"] for user, rules in acl.items()},
            },
            "amqtt.plugins.sys.broker.BrokerSysPlugin": {"sys_interval": 10},
        },
    }


def broker_config(env: Mapping[str, str], layout: Layout, hasher: Callable[[str], str] | None = None) -> Path:
    """Файл паролей (argon2, как требует FileAuthPlugin amqtt) и broker.yaml в build/local-stack/amqtt."""
    if hasher is None:
        pwdlib: Any = importlib.import_module("pwdlib")
        argon2: Any = importlib.import_module("pwdlib.hashers.argon2")
        ph = pwdlib.PasswordHash((argon2.Argon2Hasher(),))

        def hasher(password: str) -> str:
            return str(ph.hash(password))

    out = layout.state / "amqtt"
    out.mkdir(parents=True, exist_ok=True)
    passwd = out / "passwd"
    lines = [f"{user}:{hasher(password)}" for user, password in broker_users(env).items()]
    passwd.write_text("\n".join(lines) + "\n", encoding="utf-8")
    config = out / "broker.yaml"
    # JSON — подмножество YAML: amqtt читает файл yaml.safe_load
    config.write_text(json.dumps(amqtt_config(env, layout, passwd), indent=2) + "\n", encoding="utf-8")
    return config


# --- InfluxDB -----------------------------------------------------------------------------------------
_DURATION_RE = re.compile(r"^(\d+)([smhdw])$")


def duration_seconds(text: str) -> int:
    """Срок хранения InfluxDB (``30d``, ``730d``, ``24h``; ``0`` или ``inf`` — бессрочно) → секунды."""
    text = text.strip()
    if text in ("", "0", "inf", "infinite"):
        return 0
    m = _DURATION_RE.match(text)
    if not m:
        raise StackError(f"срок хранения '{text}': ожидается число и s, m, h, d или w")
    return int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[m.group(2)]


class Influx:
    """Минимальный клиент HTTP API InfluxDB 2 (стандартная библиотека)."""

    def __init__(self, url: str, token: str = "") -> None:
        self.url = url.rstrip("/")
        self.token = token

    def request(self, method: str, path: str, body: Any = None, *, raw: str | None = None) -> Any:
        data = None
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Token {self.token}"
        if raw is not None:
            data = raw.encode("utf-8")
            headers["Content-Type"] = "application/vnd.flux"
            headers["Accept"] = "application/csv"
        elif body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise StackError(f"InfluxDB {method} {path}: HTTP {exc.code} {detail}") from exc
        if raw is not None:
            return text
        return json.loads(text) if text.strip() else None

    def query(self, org: str, flux: str) -> str:
        """Flux → annotated CSV."""
        result: str = self.request("POST", "/api/v2/query?" + urllib.parse.urlencode({"org": org}), raw=flux)
        return result

    def count(self, org: str, flux: str) -> int:
        return count_from_csv(self.query(org, flux))


def influx_healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=3) as resp:
            return bool(json.loads(resp.read().decode("utf-8")).get("status") == "pass")
    except (urllib.error.URLError, OSError, ValueError):
        return False


def influx_init(env: Mapping[str, str], layout: Layout, log: Callable[[str], None] = print) -> None:
    """Первичная установка (как DOCKER_INFLUXDB_INIT_MODE=setup образа) и influxdb/influxdb-init.sh.

    Значения — из окружения сервисов influxdb и influxdb-init в docker-compose.yml; токены Telegraf
    и Grafana — в том influx-tokens (``build/local-stack/volumes/influx-tokens``). Повтор безопасен.
    """
    setup_env = compose_environment("influxdb", env)
    init_env = compose_environment("influxdb-init", env)
    org, bucket = init_env["INFLUX_ORG"], init_env["INFLUX_BUCKET"]
    admin = Influx(layout.influx_url, init_env["INFLUX_TOKEN"])
    if Influx(layout.influx_url).request("GET", "/api/v2/setup").get("allowed"):
        admin.request(
            "POST",
            "/api/v2/setup",
            {
                "username": setup_env["DOCKER_INFLUXDB_INIT_USERNAME"],
                "password": setup_env["DOCKER_INFLUXDB_INIT_PASSWORD"],
                "org": setup_env["DOCKER_INFLUXDB_INIT_ORG"],
                "bucket": setup_env["DOCKER_INFLUXDB_INIT_BUCKET"],
                "retentionPeriodSeconds": duration_seconds(setup_env["DOCKER_INFLUXDB_INIT_RETENTION"]),
                "token": setup_env["DOCKER_INFLUXDB_INIT_ADMIN_TOKEN"],
            },
        )
        log(f"influx-init: первичная установка: организация {org}, бакет {bucket}")
    orgs = admin.request("GET", "/api/v2/orgs?" + urllib.parse.urlencode({"org": org}))["orgs"]
    org_id = orgs[0]["id"]

    def bucket_id(name: str) -> str | None:
        query = urllib.parse.urlencode({"orgID": org_id, "name": name})
        try:
            found = admin.request("GET", f"/api/v2/buckets?{query}").get("buckets") or []
        except StackError as exc:
            if "HTTP 404" in str(exc):  # фильтр по имени без совпадений — 404, а не пустой список
                return None
            raise
        return str(found[0]["id"]) if found else None

    def retention(seconds: int) -> list[dict[str, Any]]:
        return [{"type": "expire", "everySeconds": seconds}] if seconds else []

    raw_id = bucket_id(bucket)
    if raw_id is None:
        raise StackError(f"нет бакета {bucket} (первичная установка не прошла?)")
    admin.request(
        "PATCH",
        f"/api/v2/buckets/{raw_id}",
        {"retentionRules": retention(duration_seconds(init_env["INFLUX_RETENTION"]))},
    )
    log(f"influx-init: бакет {bucket}: хранение {init_env['INFLUX_RETENTION']}")
    agg = init_env["INFLUX_BUCKET_AGG"]
    agg_rules = retention(duration_seconds(init_env["INFLUX_RETENTION_AGG"]))
    agg_id = bucket_id(agg)
    if agg_id is None:
        agg_id = str(
            admin.request("POST", "/api/v2/buckets", {"orgID": org_id, "name": agg, "retentionRules": agg_rules})["id"]
        )
        log(f"influx-init: создан бакет {agg}: хранение {init_env['INFLUX_RETENTION_AGG']}")
    else:
        admin.request("PATCH", f"/api/v2/buckets/{agg_id}", {"retentionRules": agg_rules})

    # Задача прореживания; уже созданная получает текущий текст из репозитория (как influxdb-init.sh)
    task_name = "kns_downsample_1h"
    flux = (ROOT / "influxdb" / "tasks" / "downsample_1h.flux").read_text(encoding="utf-8")
    flux = flux.replace("@RAW_BUCKET@", bucket).replace("@AGG_BUCKET@", agg)
    tasks = admin.request("GET", "/api/v2/tasks?" + urllib.parse.urlencode({"orgID": org_id, "name": task_name}))
    if tasks.get("tasks"):
        admin.request("PATCH", f"/api/v2/tasks/{tasks['tasks'][0]['id']}", {"flux": flux})
        log(f"influx-init: задача {task_name} обновлена из influxdb/tasks/downsample_1h.flux")
    else:
        admin.request("POST", "/api/v2/tasks", {"orgID": org_id, "flux": flux})
        log(f"influx-init: создана задача {task_name}")

    tokens = layout.map_path("influxdb-init", "/tokens")
    tokens.mkdir(parents=True, exist_ok=True)

    def ensure_token(name: str, permissions: list[dict[str, Any]]) -> None:
        token_file, id_file = tokens / f"{name}.token", tokens / f"{name}.id"
        if token_file.exists() and id_file.exists():
            try:
                admin.request("GET", f"/api/v2/authorizations/{id_file.read_text(encoding='utf-8').strip()}")
                log(f"influx-init: токен {name} уже есть")
                return
            except StackError:
                log(f"influx-init: токен {name} не найден в базе (база пересоздана?) — выпускается новый")
        auth = admin.request(
            "POST",
            "/api/v2/authorizations",
            {"orgID": org_id, "description": f"stand-{name}", "permissions": permissions},
        )
        token_file.write_text(auth["token"], encoding="utf-8")
        id_file.write_text(auth["id"], encoding="utf-8")
        log(f"influx-init: выпущен токен {name}")

    def perm(action: str, bucket_ref: str) -> dict[str, Any]:
        return {"action": action, "resource": {"type": "buckets", "id": bucket_ref, "orgID": org_id}}

    ensure_token("telegraf", [perm("write", raw_id)])
    ensure_token("grafana", [perm("read", raw_id), perm("read", agg_id)])
    log("influx-init: готово")


# --- Grafana ------------------------------------------------------------------------------------------
def grafana_provisioning(env: Mapping[str, str], layout: Layout) -> Path:
    """Копия grafana/provisioning: пути контейнера → пути хоста, адрес InfluxDB → 127.0.0.1.

    Меняются только строки, которые в контейнере даёт docker compose (тома и имя сервиса influxdb);
    каждая замена обязана сработать — иначе провиженинг разошёлся с этим переводом.
    """
    src = ROOT / "grafana" / "provisioning"
    dst = layout.state / "grafana" / "provisioning"
    if dst.exists():
        shutil.rmtree(dst)
    replaced: set[str] = set()
    needed = {"/run/influx-tokens/grafana.token", "/etc/grafana/dashboards", "http://influxdb:8086"}
    for path in sorted(src.rglob("*")):
        if path.is_dir():
            continue
        text = path.read_text(encoding="utf-8")
        for container in sorted(needed, key=len, reverse=True):
            if container in text:
                host = (
                    layout.rewrite_hosts(container)
                    if container.startswith("http")
                    else posix(layout.map_path("grafana", container))
                )
                text = text.replace(container, host)
                replaced.add(container)
        out = dst / path.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    missing = needed - replaced
    if missing:
        raise StackError(f"grafana/provisioning: не найдены строки для перевода на хост: {sorted(missing)}")
    return dst


def grafana_get(layout: Layout, env: Mapping[str, str], path: str) -> Any:
    req = urllib.request.Request(layout.grafana_url + path)
    auth = base64.b64encode(
        f"{env.get('GRAFANA_ADMIN_USER', 'admin')}:{env.get('GRAFANA_ADMIN_PASSWORD', '')}".encode()
    )
    req.add_header("Authorization", "Basic " + auth.decode())
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --- готовность ---------------------------------------------------------------------------------------
def tcp_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return bool(200 <= resp.status < 300)
    except (urllib.error.URLError, OSError):
        return False


def mqtt_login_ok(env: Mapping[str, str], layout: Layout) -> bool:
    """Вход пользователя мониторинга по паролю — то же, что healthcheck mosquitto в compose."""
    try:
        mqtt: Any = importlib.import_module("paho.mqtt.client")
    except ImportError:
        return tcp_open(layout.mqtt_port)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"local-stack-health-{os.getpid()}")
    client.username_pw_set(env.get("MQTT_MONITOR_USER", "monitor"), env.get("MQTT_MONITOR_PASSWORD", ""))
    try:
        client.connect("127.0.0.1", layout.mqtt_port, keepalive=10)
        rc = client.loop(timeout=3)
        ok = rc == 0 and client.is_connected()
        client.disconnect()
        return bool(ok)
    except OSError:
        return False


def healthy(name: str, env: Mapping[str, str], layout: Layout) -> bool:
    if name == "broker":
        return mqtt_login_ok(env, layout)
    if name == "influxdb":
        return influx_healthy(layout.influx_url)
    if name == "telegraf":
        return http_ok(f"http://127.0.0.1:{layout.telegraf_health_port}/")
    if name == "grafana":
        return http_ok(layout.grafana_url + "/api/health")
    if name == "emulator":
        return tcp_open(layout.opcua_port)
    raise StackError(f"неизвестный сервис {name}")


def wait_for(name: str, env: Mapping[str, str], layout: Layout, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if healthy(name, env, layout):
            return True
        time.sleep(1)
    return healthy(name, env, layout)


def wait_data(env: Mapping[str, str], layout: Layout, timeout: float) -> bool:
    """Критерий «данные на дашбордах» (как stack_wait.py --data), запросы — по HTTP API."""
    org, bucket = env.get("INFLUX_ORG", "vodokanal"), env.get("INFLUX_BUCKET", "kns_raw")
    admin = Influx(layout.influx_url, env["INFLUX_ADMIN_TOKEN"])
    # те же запросы, что у stack_wait.py: данные прошлого запуска в базе не засчитываются
    telemetry = telemetry_flux(bucket, time.time() - FRESH_MARGIN_S)
    birth = birth_flux(bucket)
    started = time.monotonic()
    last = ""
    while True:
        try:
            points, online = admin.count(org, telemetry), admin.count(org, birth)
        except StackError:
            points = online = 0
        try:
            boards = {d.get("uid", "") for d in grafana_get(layout, env, "/api/search?tag=kns1")}
        except (urllib.error.URLError, OSError, ValueError):
            boards = set()
        missing = [uid for uid in DASHBOARD_UIDS if uid not in boards]
        state = (
            f"свежих точек LT101/level — {points}, PLC1 online — {'да' if online else 'нет'},"
            f" дашбордов нет — {', '.join(missing) or '0'}"
        )
        if state != last:
            print(f"[{time.monotonic() - started:5.0f} с] {state}", flush=True)
            last = state
        if points and online and not missing:
            return True
        if time.monotonic() - started > timeout:
            return False
        time.sleep(5)


# --- установка ----------------------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def install(layout: Layout, log: Callable[[str], None] = print) -> None:
    """Скачать сборки в <tools>/_dl, сверить SHA-256, распаковать каждую в свой каталог; venv amqtt."""
    dl = layout.tools / "_dl"
    dl.mkdir(parents=True, exist_ok=True)
    for c in COMPONENTS:
        target = layout.tools / c.name
        if target.exists() and any(target.rglob(f"{'influxd' if c.name == 'influxdb' else c.name}.exe")):
            log(f"{c.name} {c.version}: уже установлен в {target}")
            continue
        archive = dl / c.url.rsplit("/", 1)[1]
        if not archive.exists() or sha256_file(archive) != c.sha256:
            log(f"{c.name} {c.version}: загрузка {c.url}")
            with urllib.request.urlopen(c.url, timeout=60) as resp, archive.open("wb") as out:
                shutil.copyfileobj(resp, out, 1 << 20)
        digest = sha256_file(archive)
        if digest != c.sha256:
            archive.unlink()
            raise StackError(f"{archive.name}: SHA-256 {digest}, ожидался {c.sha256}")
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                resolved = (target / member).resolve()
                if not str(resolved).startswith(str(target.resolve())):
                    raise StackError(f"{archive.name}: путь вне каталога распаковки: {member}")
            zf.extractall(target)
        log(f"{c.name} {c.version}: распакован в {target}")
    venv = layout.tools / "amqtt" / "venv"
    if not layout.amqtt_python.exists():
        log(f"amqtt {AMQTT_VERSION}: venv {venv}")
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    subprocess.run(
        [
            str(layout.amqtt_python),
            "-m",
            "pip",
            "install",
            "-q",
            "--disable-pip-version-check",
            f"amqtt=={AMQTT_VERSION}",
            f"tzdata=={TZDATA_VERSION}",
        ],
        check=True,
    )
    log(f"amqtt {AMQTT_VERSION}, tzdata {TZDATA_VERSION}: установлены в {venv}")
    subprocess.run([str(layout.amqtt_python), str(Path(__file__).resolve()), "zoneinfo-zip"], check=True)


def zoneinfo_zip(layout: Layout) -> Path:
    """Архив часовых поясов для Go (переменная ZONEINFO influxd) из пакета tzdata (база IANA).

    Сборка InfluxDB для Windows базы поясов не содержит (в образе alpine она есть — пакет tzdata),
    и ``timezone.location()`` во Flux (дашборд «Насосы») без неё не работает. Go читает из архива
    только несжатые записи с именами вида ``Europe/Moscow``. Запускается интерпретатором venv amqtt.
    """
    tzdata: Any = importlib.import_module("tzdata")
    src = Path(tzdata.__file__).parent / "zoneinfo"
    out = layout.tools / "influxdb" / "zoneinfo.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED) as zf:
        for path in sorted(src.rglob("*")):
            if path.is_file() and not path.name.startswith("__") and path.suffix not in (".py", ".pyc", ".zi", ".tab"):
                zf.write(path, path.relative_to(src).as_posix())
    print(f"zoneinfo-zip: {out}")
    return out


# --- командная строка ---------------------------------------------------------------------------------
def status(env: Mapping[str, str], layout: Layout) -> int:
    print(f"{'сервис':<10} {'PID':>7}  {'здоров':<6}  адрес")
    addresses = {
        "broker": f"mqtt://127.0.0.1:{layout.mqtt_port}",
        "influxdb": layout.influx_url,
        "telegraf": f"http://127.0.0.1:{layout.telegraf_health_port}/ (health)",
        "grafana": layout.grafana_url,
        "emulator": f"opc.tcp://127.0.0.1:{layout.opcua_port}",
    }
    all_ok = True
    for name in SERVICES:
        found = running_pid(layout, name)
        pid = str(found) if found is not None else "—"
        ok = healthy(name, env, layout)
        all_ok &= ok or name == "emulator"
        print(f"{name:<10} {pid:>7}  {'да' if ok else 'нет':<6}  {addresses[name]}")
    return 0 if all_ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Локальный стенд КНС-1 без Docker (см. local_stack.ps1)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("install", help="скачать сборки и создать venv amqtt")
    sub.add_parser("zoneinfo-zip", help="архив часовых поясов для influxd (интерпретатор venv amqtt)")
    p_spec = sub.add_parser("spec", help="JSON запуска сервиса")
    p_spec.add_argument("name", choices=SERVICES)
    p_launch = sub.add_parser("launch", help="запустить сервис отдельным процессом")
    p_launch.add_argument("name", choices=SERVICES)
    p_stop = sub.add_parser("stop", help="остановить сервис")
    p_stop.add_argument("name", choices=SERVICES)
    sub.add_parser("broker-config", help="конфигурация amqtt (интерпретатор venv amqtt)")
    sub.add_parser("influx-init", help="настройка InfluxDB через HTTP API")
    sub.add_parser("grafana-provisioning", help="провиженинг Grafana с путями хоста")
    p_wait = sub.add_parser("wait", help="ждать готовности сервиса")
    p_wait.add_argument("name", choices=SERVICES)
    p_wait.add_argument("--timeout", type=float, default=60.0)
    p_data = sub.add_parser("wait-data", help="ждать данных на дашбордах")
    p_data.add_argument("--timeout", type=float, default=300.0)
    sub.add_parser("status", help="состояние сервисов")
    args = ap.parse_args(argv)

    try:
        if args.cmd == "install":
            install(Layout.from_env({}))
            return 0
        if args.cmd == "zoneinfo-zip":
            zoneinfo_zip(Layout.from_env({}))
            return 0
        env = load_env()
        layout = Layout.from_env(env)
        if args.cmd == "spec":
            print(json.dumps(spec(args.name, env, layout), ensure_ascii=True))
        elif args.cmd == "launch":
            print(f"{args.name}: PID {launch(args.name, env, layout)}")
        elif args.cmd == "stop":
            pid = stop(args.name, layout)
            if pid is not None:
                print(f"{args.name}: остановлен (PID {pid})")
        elif args.cmd == "broker-config":
            print(f"broker-config: {broker_config(env, layout)}")
        elif args.cmd == "influx-init":
            influx_init(env, layout)
        elif args.cmd == "grafana-provisioning":
            print(f"grafana-provisioning: {grafana_provisioning(env, layout)}")
        elif args.cmd == "wait":
            if not wait_for(args.name, env, layout, args.timeout):
                print(
                    f"{args.name}: не готов за {args.timeout:.0f} с (журнал: {layout.state / 'logs'})", file=sys.stderr
                )
                return 1
        elif args.cmd == "wait-data":
            if not wait_data(env, layout, args.timeout):
                print("данные не появились: журналы эмулятора и Telegraf в build/local-stack/logs", file=sys.stderr)
                return 1
            print(f"данные на дашбордах: {layout.grafana_url}/d/kns1-overview (логин — GRAFANA_ADMIN_* в .env)")
        elif args.cmd == "status":
            return status(env, layout)
    except StackError as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
