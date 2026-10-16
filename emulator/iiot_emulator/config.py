"""Настройки эмулятора из переменных окружения (и необязательного файла .env).

Секреты (пароли OPC UA и MQTT) — только в окружении или в ``.env``, который не попадает в git;
в репозитории — ``.env.example``. Все переменные эмулятора начинаются с ``EMU_``: docker compose
передаёт в них значения общего ``.env`` стенда.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


def load_env_file(path: Path, environ: dict[str, str] | None = None) -> dict[str, str]:
    """Прочитать ``KEY=VALUE`` из файла .env; уже заданные переменные окружения не трогаются."""
    target = os.environ if environ is None else environ
    loaded: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        loaded[key] = value
        target.setdefault(key, value)
    return loaded


def _bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key, "").strip()
    return float(raw) if raw else default


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "").strip()
    return int(raw) if raw else default


def _str(env: Mapping[str, str], key: str, default: str) -> str:
    raw = env.get(key)
    return raw.strip() if raw is not None and raw.strip() != "" else default


@dataclass(frozen=True)
class SimSettings:
    seed: int = 1
    time_factor: float = 60.0  # модельных секунд за секунду реального времени
    step_s: float = 1.0  # модельный шаг цикла ПЛК
    tick_s: float = 0.25  # период обмена с OPC UA и MQTT, реальные секунды
    start_hour: float = 6.0
    auto_faults: bool = True
    auto_ack_s: float = 900.0


@dataclass(frozen=True)
class OpcUaSettings:
    enable: bool = True
    endpoint: str = "opc.tcp://0.0.0.0:4840"
    user: str = ""
    password: str = field(default="", repr=False)
    allow_anonymous: bool = False  # анонимно — только чтение
    pki_dir: Path = Path("pki")
    hostname: str = ""  # имя в сертификате; пусто — имя компьютера
    namespace_index: int = 4
    device_name: str = "CODESYS Control Win V3"


@dataclass(frozen=True)
class MqttSettings:
    enable: bool = True
    host: str = "localhost"
    port: int = 1883
    user: str = ""
    password: str = field(default="", repr=False)
    tls: bool = False
    ca_file: str = ""
    tls_insecure: bool = False  # только для самоподписанного сертификата стенда без имени хоста
    client_id: str = "kns-emulator"
    keepalive_s: int = 30
    period_s: float = 60.0  # контрольная публикация всех метрик
    cmd_max_age_s: float = 30.0
    cmd_rate_limit: int = 10
    cmd_rate_window_s: float = 10.0
    site: str = ""  # пусто — из topics.json
    area: str = ""
    unit: str = ""
    node: str = ""


@dataclass(frozen=True)
class Settings:
    sim: SimSettings = field(default_factory=SimSettings)
    opcua: OpcUaSettings = field(default_factory=OpcUaSettings)
    mqtt: MqttSettings = field(default_factory=MqttSettings)
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        sim = SimSettings(
            seed=_int(e, "EMU_SEED", 1),
            time_factor=_float(e, "EMU_TIME_FACTOR", 60.0),
            step_s=_float(e, "EMU_STEP_S", 1.0),
            tick_s=_float(e, "EMU_TICK_S", 0.25),
            start_hour=_float(e, "EMU_START_HOUR", 6.0),
            auto_faults=_bool(e, "EMU_AUTO_FAULTS", True),
            auto_ack_s=_float(e, "EMU_AUTO_ACK_S", 900.0),
        )
        opcua = OpcUaSettings(
            enable=_bool(e, "EMU_OPCUA_ENABLE", True),
            endpoint=_str(e, "EMU_OPCUA_ENDPOINT", "opc.tcp://0.0.0.0:4840"),
            user=_str(e, "EMU_OPCUA_USER", ""),
            password=e.get("EMU_OPCUA_PASSWORD", ""),
            allow_anonymous=_bool(e, "EMU_OPCUA_ALLOW_ANONYMOUS", False),
            pki_dir=Path(_str(e, "EMU_OPCUA_PKI_DIR", "pki")),
            hostname=_str(e, "EMU_OPCUA_HOSTNAME", ""),
            namespace_index=_int(e, "EMU_OPCUA_NS", 4),
            device_name=_str(e, "EMU_OPCUA_DEVICE_NAME", "CODESYS Control Win V3"),
        )
        tls = _bool(e, "EMU_MQTT_TLS", False)
        mqtt = MqttSettings(
            enable=_bool(e, "EMU_MQTT_ENABLE", True),
            host=_str(e, "EMU_MQTT_HOST", "localhost"),
            port=_int(e, "EMU_MQTT_PORT", 8883 if tls else 1883),
            user=_str(e, "EMU_MQTT_USER", ""),
            password=e.get("EMU_MQTT_PASSWORD", ""),
            tls=tls,
            ca_file=_str(e, "EMU_MQTT_CA_FILE", ""),
            tls_insecure=_bool(e, "EMU_MQTT_TLS_INSECURE", False),
            client_id=_str(e, "EMU_MQTT_CLIENT_ID", "kns-emulator"),
            keepalive_s=_int(e, "EMU_MQTT_KEEPALIVE_S", 30),
            period_s=_float(e, "EMU_MQTT_PERIOD_S", 60.0),
            cmd_max_age_s=_float(e, "EMU_MQTT_CMD_MAX_AGE_S", 30.0),
            cmd_rate_limit=_int(e, "EMU_MQTT_CMD_RATE_LIMIT", 10),
            cmd_rate_window_s=_float(e, "EMU_MQTT_CMD_RATE_WINDOW_S", 10.0),
            site=_str(e, "EMU_MQTT_SITE", ""),
            area=_str(e, "EMU_MQTT_AREA", ""),
            unit=_str(e, "EMU_MQTT_UNIT", ""),
            node=_str(e, "EMU_MQTT_NODE", ""),
        )
        return cls(sim=sim, opcua=opcua, mqtt=mqtt, log_level=_str(e, "EMU_LOG_LEVEL", "INFO").upper())
