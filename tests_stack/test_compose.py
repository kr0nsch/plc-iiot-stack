"""docker compose: закреплённые образы, проверки здоровья, сеть, тома, порты и секреты."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

import stack_catalog as sc
from stack_model import env_refs

REPO = sc.REPO
COMPOSE_FILES = ["docker-compose.yml", "docker-compose.tls.yml", "docker-compose.dev.yml"]
# Версия образа: x.y или x.y.z с необязательным суффиксом варианта (-alpine, -22); latest и плавающие — нет
PINNED_TAG = re.compile(r"^\d+\.\d+(\.\d+)?(-[a-z0-9]+)*$")
ONE_SHOT = {"influxdb-init"}
PUBLISHED = {"mosquitto", "grafana", "nodered"}
SECRET_WORDS = re.compile(r"PASSWORD|TOKEN|SECRET", re.I)


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((REPO / name).read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def compose() -> dict[str, Any]:
    return load("docker-compose.yml")


@pytest.fixture(scope="module")
def services(compose: dict[str, Any]) -> dict[str, dict[str, Any]]:
    svc: dict[str, dict[str, Any]] = compose["services"]
    return svc


def env_example() -> dict[str, str]:
    out = {}
    for line in (REPO / ".env.example").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


@pytest.mark.parametrize("name", COMPOSE_FILES)
def test_compose_files_parse(name: str) -> None:
    assert isinstance(load(name)["services"], dict)


def test_images_are_pinned(services: dict[str, dict[str, Any]]) -> None:
    for name, svc in services.items():
        image = svc["image"]
        repo, _, tag = image.rpartition(":")
        if "build" in svc:
            assert tag == "local", f"{name}: собираемый образ помечается :local"
            continue
        assert repo and PINNED_TAG.match(tag), f"{name}: образ {image} не закреплён по версии"


def test_component_versions(services: dict[str, dict[str, Any]]) -> None:
    """Mosquitto 2.x, InfluxDB 2.x (не 3.x), Grafana OSS (grafana/grafana, не enterprise)."""
    assert services["mosquitto"]["image"].startswith("eclipse-mosquitto:2.")
    assert services["influxdb"]["image"].startswith("influxdb:2.")
    assert services["influxdb-init"]["image"] == services["influxdb"]["image"]
    assert services["telegraf"]["image"].startswith("telegraf:1.")
    assert services["grafana"]["image"].startswith("grafana/grafana:")
    assert services["nodered"]["profiles"] == ["nodered"]
    assert services["emulator"]["profiles"] == ["demo"]


def test_dockerfile_base_image_pinned() -> None:
    text = (REPO / "docker" / "emulator.Dockerfile").read_text(encoding="utf-8")
    bases = re.findall(r"^FROM\s+(\S+)", text, re.M)
    assert bases and all(PINNED_TAG.match(b.rpartition(":")[2]) for b in bases), bases


def test_healthchecks_restart_and_network(services: dict[str, dict[str, Any]], compose: dict[str, Any]) -> None:
    assert compose["networks"]["iiot"]["driver"] == "bridge"
    for name, svc in services.items():
        assert svc["networks"] == ["iiot"], name
        assert "no-new-privileges:true" in svc["security_opt"], name
        assert svc["logging"]["options"]["max-size"], name
        if name in ONE_SHOT:
            assert svc["restart"] == "no" and "healthcheck" not in svc
        else:
            assert svc["restart"] == "unless-stopped", name
            if name != "nodered":  # у образа Node-RED своя HEALTHCHECK
                assert svc["healthcheck"]["test"], name


def test_dependencies_wait_for_health(services: dict[str, dict[str, Any]]) -> None:
    dep = services["telegraf"]["depends_on"]
    assert dep["mosquitto"]["condition"] == "service_healthy"
    assert dep["influxdb"]["condition"] == "service_healthy"
    assert dep["influxdb-init"]["condition"] == "service_completed_successfully"
    assert services["grafana"]["depends_on"]["influxdb-init"]["condition"] == "service_completed_successfully"


def test_volumes_are_named_or_repo_binds(services: dict[str, dict[str, Any]], compose: dict[str, Any]) -> None:
    declared = set(compose["volumes"])
    used = set()
    for name, svc in services.items():
        for vol in svc.get("volumes", []):
            source, target, *mode = vol.split(":")
            if source.startswith("./"):
                assert (REPO / source).exists(), f"{name}: нет {source}"
                assert mode == ["ro"], f"{name}: конфигурация из репозитория монтируется только для чтения"
            else:
                assert source in declared, f"{name}: том {source} не объявлен"
                used.add(source)
            assert target.startswith("/")
    assert used == declared


def test_only_grafana_and_mqtt_published(services: dict[str, dict[str, Any]]) -> None:
    for name, svc in services.items():
        if name not in PUBLISHED:
            assert "ports" not in svc, f"{name}: порт на хост не нужен"
            continue
        for port in svc["ports"]:
            host_ip = port.split("}:")[0] + "}" if port.startswith("${") else port.split(":")[0]
            assert host_ip in ("127.0.0.1", "${MQTT_BIND:-127.0.0.1}", "${GRAFANA_BIND:-127.0.0.1}"), port
    dev = load("docker-compose.dev.yml")["services"]
    assert set(dev) == {"influxdb"} and dev["influxdb"]["ports"][0].startswith("127.0.0.1:")
    tls = load("docker-compose.tls.yml")["services"]["mosquitto"]
    assert tls["environment"]["MQTT_TLS"] == "true" and tls["ports"][0].endswith(":8883")


def test_secrets_only_from_env(services: dict[str, dict[str, Any]]) -> None:
    for name, svc in services.items():
        for key, value in (svc.get("environment") or {}).items():
            if SECRET_WORDS.search(key) and not key.endswith(("_FILE", "_USER")):
                assert str(value).startswith("${"), f"{name}.{key}: секрет не из .env"


def test_env_example_covers_compose_variables() -> None:
    example = env_example()
    used = set()
    for name in COMPOSE_FILES:
        used |= env_refs((REPO / name).read_text(encoding="utf-8"))
    assert used <= set(example), f"нет в .env.example: {sorted(used - set(example))}"
    for key, value in example.items():
        if SECRET_WORDS.search(key) and not key.startswith(("OPCUA_",)):
            assert value in ("change-me", ""), f"{key}: в .env.example только заглушка change-me (или пусто)"


def test_required_secrets_fail_fast(compose: dict[str, Any]) -> None:
    """Без .env compose не стартует молча с пустыми паролями: обязательные секреты — ${VAR:?…}."""
    text = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    for key in env_refs(text):
        if SECRET_WORDS.search(key) and not key.startswith("OPCUA_"):
            assert re.search(rf"\$\{{{key}:\?", text), key


def tracked_files() -> list[Path]:
    """Файлы, которые попадут в git: отслеживаемые и новые, не исключённые .gitignore."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=REPO,
            capture_output=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git недоступен")
    return [REPO / p for p in out.decode("utf-8").split("\0") if p]


# Заголовок PEM закрытого ключа (строка собрана из частей, чтобы тест не находил сам себя)
PEM_PRIVATE_KEY = re.compile("-----BEGIN [A-Z ]*" + "PRIVATE KEY-----")
CONFIG_SUFFIXES = {".yml", ".yaml", ".conf", ".toml", ".json", ".sh", ".ps1", ".template", ".flux", ".example"}
ASSIGNMENT = re.compile(
    r"(?i)(password|passwd|token|secret)[\"']?[ \t]*[:=][ \t]*[\"']?(?!\$|change-me|\{|<)([A-Za-z0-9_\-+/=]{16,})"
)


def test_no_secrets_in_tracked_files() -> None:
    files = tracked_files()
    names = {p.relative_to(REPO).as_posix() for p in files}
    assert ".env" not in names, ".env не должен попадать в git"
    assert not [n for n in names if n.startswith("mosquitto/certs/") and n != "mosquitto/certs/.gitignore"]
    for path in files:
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(REPO).as_posix()
        assert not PEM_PRIVATE_KEY.search(text), f"{rel}: закрытый ключ"
        if path.suffix in CONFIG_SUFFIXES or path.name in ("Makefile", ".env.example"):
            found = ASSIGNMENT.search(text)
            assert not found, f"{rel}: похоже на секрет: {found.group(0)[:40]}"


def test_mqtt_tls_listener_is_hardened() -> None:
    """Слушатель TLS: минимум TLS 1.2 явно, сертификаты из каталога, который готовит entrypoint."""
    lines = [
        line.split()
        for line in (REPO / "mosquitto" / "config" / "tls.conf").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    opts = {words[0]: words[1:] for words in lines}
    assert opts["listener"] == ["8883"]
    assert opts["tls_version"] == ["tlsv1.2"]
    for key in ("cafile", "certfile", "keyfile"):
        assert opts[key][0].startswith("/mosquitto/run/certs/"), key
    assert "allow_anonymous" not in opts, "анонимный доступ задаётся только общим mosquitto.conf (false)"


def test_influxdb_init_keeps_task_in_sync() -> None:
    """Уже созданная задача прореживания получает текст из репозитория (а не остаётся старой навсегда)."""
    script = (REPO / "influxdb" / "influxdb-init.sh").read_text(encoding="utf-8")
    assert 'influx task update --id "$task_id" --file "$tmp"' in script
    assert 'influx task create --org "$INFLUX_ORG" --file "$tmp"' in script
    local = (REPO / "tools_project" / "local_stack.py").read_text(encoding="utf-8")
    assert '"PATCH", f"/api/v2/tasks/' in local
    task = (REPO / "influxdb" / "tasks" / "downsample_1h.flux").read_text(encoding="utf-8")
    assert "events.duration(" in task, "mean — взвешенное по времени"
    assert 'r.quality != "bad"' in task


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def test_emulator_constraints_pin_whole_dependency_tree() -> None:
    """Образ эмулятора: закреплены прямые и транзитивные зависимости (Linux), каждая — точной версией."""
    md = pytest.importorskip("importlib.metadata")
    req_mod = pytest.importorskip("packaging.requirements")
    markers = pytest.importorskip("packaging.markers")
    pins: dict[str, str] = {}
    for line in (REPO / "docker" / "emulator-constraints.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, sep, version = line.partition("==")
            assert sep and version, f"не точная версия: {line}"
            pins[_norm(name)] = version
    try:
        md.distribution("asyncua")
    except md.PackageNotFoundError:
        pytest.skip("эмулятор не установлен (задание packages ставит его с этими ограничениями)")
    env = {**markers.default_environment(), "sys_platform": "linux", "platform_system": "Linux", "os_name": "posix"}
    seen: dict[str, str] = {}

    def walk(name: str) -> None:
        key = _norm(name)
        if key in seen:
            return
        dist = md.distribution(name)
        seen[key] = dist.version
        for raw in dist.requires or []:
            req = req_mod.Requirement(raw)
            if req.marker is None or req.marker.evaluate({**env, "extra": ""}):
                walk(req.name)

    for top in ("asyncua", "paho-mqtt", "cryptography"):
        walk(top)
    missing = sorted(set(seen) - set(pins))
    assert not missing, f"не закреплены в docker/emulator-constraints.txt: {missing}"
    differ = {k: (pins[k], v) for k, v in seen.items() if pins[k] != v}
    assert not differ, f"закреплённая версия ≠ проверенной в тестах (закреплено, установлено): {differ}"
