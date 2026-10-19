"""Локальный стенд без Docker (tools_project/local_stack.py, local_stack.ps1) и проверка панелей дашбордов.

Сами сервисы здесь не запускаются: проверяется перевод конфигурации docker compose на хост — те же
пользователи и ACL брокера, те же переменные Telegraf и Grafana, пути томов, версии сборок.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

import check_dashboards as cd
import local_stack as ls
import stack_catalog as sc

ENV = {
    "MQTT_TOPIC_ROOT": "vodokanal",
    "MQTT_PLC_USER": "plc",
    "MQTT_PLC_PASSWORD": "p1-secret",
    "MQTT_TELEGRAF_USER": "telegraf",
    "MQTT_TELEGRAF_PASSWORD": "p2-secret",
    "MQTT_OPERATOR_USER": "operator",
    "MQTT_OPERATOR_PASSWORD": "p3-secret",
    "MQTT_MONITOR_USER": "monitor",
    "MQTT_MONITOR_PASSWORD": "p4-secret",
    "INFLUX_ADMIN_PASSWORD": "admin-secret",
    "INFLUX_ADMIN_TOKEN": "admin-token",
    "GRAFANA_ADMIN_PASSWORD": "grafana-secret",
    "GRAFANA_SECRET_KEY": "grafana-key",
    "OPCUA_ENDPOINT": "opc.tcp://emulator:4840",
    "OPCUA_ID_PREFIX": "|var|CODESYS Control Win V3.",
}


@pytest.fixture
def layout(tmp_path: Path) -> ls.Layout:
    return ls.Layout(
        state=tmp_path / "state",
        tools=tmp_path / "tools",
        mqtt_port=1883,
        influx_port=8086,
        grafana_port=3000,
        opcua_port=4841,
        telegraf_health_port=8080,
    )


def fake_tools(layout: ls.Layout) -> None:
    for rel in (
        "influxdb/influxd.exe",
        "telegraf/telegraf-1.39.3/telegraf.exe",
        "grafana/grafana-12.4.12/bin/grafana.exe",
        "amqtt/venv/Scripts/amqtt.exe",
    ):
        path = layout.tools / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")


# --- подстановка переменных и окружение compose -------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("${A}", "a"),
        ("${MISSING:-d}", "d"),
        ("${EMPTY:-d}", "d"),
        ("${EMPTY-d}", ""),
        ("${MISSING-d}", "d"),
        ("x$${A}y", "x${A}y"),
        ("$A/$B", "a/"),
    ],
)
def test_interpolate_follows_compose(text: str, expected: str) -> None:
    assert ls.interpolate(text, {"A": "a", "EMPTY": ""}) == expected


def test_interpolate_required_variable() -> None:
    with pytest.raises(ls.StackError, match="не задан"):
        ls.interpolate("${X:?X не задан}", {})


def test_unquote_matches_compose_env_file() -> None:
    assert ls.unquote('"|var|CODESYS Control Win V3."') == "|var|CODESYS Control Win V3."
    assert ls.unquote("plain") == "plain"


def test_load_env_prefers_process_environment(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('OPCUA_USERNAME=\nOPCUA_PASSWORD="from-file"\nMQTT_PORT=1883\n', encoding="utf-8")
    shell = {"OPCUA_USERNAME": "reader", "OPCUA_PASSWORD": "from-shell", "NOT_IN_FILE": "x"}
    values = ls.load_env(env_file, environ=shell)
    assert values == {"OPCUA_USERNAME": "reader", "OPCUA_PASSWORD": "from-shell", "MQTT_PORT": "1883"}
    assert ls.load_env(env_file, environ={})["OPCUA_PASSWORD"] == "from-file"


def test_components_match_compose_images() -> None:
    images = {s.get("image") for s in ls.compose_services().values()}
    for c in ls.COMPONENTS:
        assert c.image in images, f"{c.name} {c.version}: в docker-compose.yml нет образа {c.image}"
        assert c.version in c.url and re.fullmatch(r"[0-9a-f]{64}", c.sha256)
        assert c.url.startswith(("https://dl.influxdata.com/", "https://dl.grafana.com/oss/"))


def test_rewrite_hosts(layout: ls.Layout) -> None:
    assert layout.rewrite_hosts("tcp://mosquitto:1883") == "tcp://127.0.0.1:1883"
    assert layout.rewrite_hosts("http://influxdb:8086") == "http://127.0.0.1:8086"
    assert layout.rewrite_hosts("opc.tcp://emulator:4840") == "opc.tcp://127.0.0.1:4841"
    assert layout.rewrite_hosts("mosquitto") == "127.0.0.1"
    assert layout.rewrite_hosts("vodokanal") == "vodokanal"


def test_map_path_uses_compose_volumes(layout: ls.Layout) -> None:
    assert layout.map_path("telegraf", "/etc/telegraf/lookup") == (sc.REPO / "telegraf" / "lookup").resolve()
    assert layout.map_path("grafana", "/run/influx-tokens/grafana.token") == (
        layout.state / "volumes" / "influx-tokens" / "grafana.token"
    )
    # том токенов один и тот же у influxdb-init (пишет) и у Grafana и Telegraf (читают)
    assert layout.map_path("influxdb-init", "/tokens") == layout.state / "volumes" / "influx-tokens"
    with pytest.raises(ls.StackError, match="не смонтирован"):
        layout.map_path("grafana", "/etc/passwd")


def test_duration_seconds() -> None:
    assert ls.duration_seconds("30d") == 30 * 86400
    assert ls.duration_seconds("24h") == 86400
    assert ls.duration_seconds("0") == 0
    with pytest.raises(ls.StackError):
        ls.duration_seconds("30 days")


# --- спецификации запуска -----------------------------------------------------------------------------
def test_telegraf_spec(layout: ls.Layout) -> None:
    fake_tools(layout)
    token = layout.state / "volumes" / "influx-tokens" / "telegraf.token"
    token.parent.mkdir(parents=True)
    token.write_text("tg-token\n", encoding="utf-8")
    s = ls.spec("telegraf", ENV, layout)
    env = s["env"]
    compose_env = ls.compose_services()["telegraf"]["environment"]
    # те же переменные, что в контейнере; файл токена заменён самим токеном (как в entrypoint)
    assert set(compose_env) - {"INFLUX_TOKEN_FILE"} <= set(env)
    assert env["INFLUX_TOKEN"] == "tg-token"
    assert env["MQTT_URL"] == "tcp://127.0.0.1:1883"
    assert env["INFLUX_URL"] == "http://127.0.0.1:8086"
    assert env["OPCUA_ENDPOINT"] == "opc.tcp://127.0.0.1:4841"
    assert env["OPCUA_ID_PREFIX"] == "|var|CODESYS Control Win V3."
    assert env["MQTT_TELEGRAF_PASSWORD"] == "p2-secret"
    assert env["TELEGRAF_LOOKUP_DIR"].endswith("telegraf/lookup")
    assert s["args"][:2] == ["--config", str((sc.REPO / "telegraf" / "telegraf.conf").resolve())]
    assert "--config-directory" in s["args"]


def test_telegraf_opcua_client_certificate(layout: ls.Layout) -> None:
    """Как telegraf/docker-entrypoint.sh: сертификат клиента — только с политикой не None, в томе telegraf-pki."""
    fake_tools(layout)
    token = layout.state / "volumes" / "influx-tokens" / "telegraf.token"
    token.parent.mkdir(parents=True)
    token.write_text("tg-token", encoding="utf-8")
    env = ls.spec("telegraf", ENV, layout)["env"]
    assert env["OPCUA_CERTIFICATE"] == "" and env["OPCUA_PRIVATE_KEY"] == ""
    secure = {**ENV, "OPCUA_SECURITY_POLICY": "Basic256Sha256", "OPCUA_SECURITY_MODE": "SignAndEncrypt"}
    env = ls.spec("telegraf", secure, layout)["env"]
    pki = (layout.state / "volumes" / "telegraf-pki").as_posix()
    assert env["OPCUA_CERTIFICATE"] == f"{pki}/cert.pem"
    assert env["OPCUA_PRIVATE_KEY"] == f"{pki}/key.pem"
    env = ls.spec("telegraf", {**secure, "OPCUA_CERTIFICATE": "C:/pki/tg.pem"}, layout)["env"]
    assert env["OPCUA_CERTIFICATE"] == "C:/pki/tg.pem"


def test_telegraf_spec_needs_token(layout: ls.Layout) -> None:
    fake_tools(layout)
    with pytest.raises(ls.StackError, match="токена"):
        ls.spec("telegraf", ENV, layout)


def test_grafana_spec(layout: ls.Layout) -> None:
    fake_tools(layout)
    env = ls.spec("grafana", ENV, layout)["env"]
    assert env["GF_SECURITY_ADMIN_PASSWORD"] == "grafana-secret"
    assert env["GF_SECURITY_SECRET_KEY"] == "grafana-key", "свой ключ шифрования секретов, не общий по умолчанию"
    assert env["GF_AUTH_ANONYMOUS_ENABLED"] == "false"
    assert env["GF_SERVER_HTTP_ADDR"] == "127.0.0.1"
    assert (
        Path(env["GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH"])
        == (sc.REPO / "grafana" / "dashboards" / "kns1-overview.json").resolve()
    )
    assert Path(env["GF_PATHS_PROVISIONING"]) == layout.state / "grafana" / "provisioning"


def test_grafana_anonymous_only_on_request(layout: ls.Layout, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_tools(layout)
    monkeypatch.setenv("LOCAL_GRAFANA_ANONYMOUS", "1")
    env = ls.spec("grafana", ENV, layout)["env"]
    assert env["GF_AUTH_ANONYMOUS_ENABLED"] == "true" and env["GF_AUTH_ANONYMOUS_ORG_ROLE"] == "Viewer"


def test_emulator_spec(layout: ls.Layout) -> None:
    env = ls.spec("emulator", ENV, layout)["env"]
    assert env["EMU_MQTT_HOST"] == "127.0.0.1"
    assert env["EMU_MQTT_PASSWORD"] == "p1-secret"
    assert env["EMU_OPCUA_ENDPOINT"] == "opc.tcp://127.0.0.1:4841"
    assert env["EMU_OPCUA_HOSTNAME"] == "127.0.0.1"


def test_influxdb_spec_binds_localhost(layout: ls.Layout) -> None:
    fake_tools(layout)
    env = ls.spec("influxdb", ENV, layout)["env"]
    assert env["INFLUXD_HTTP_BIND_ADDRESS"] == "127.0.0.1:8086"
    assert env["INFLUXD_REPORTING_DISABLED"] == "true"
    assert Path(env["INFLUXD_BOLT_PATH"]).parent == layout.state / "volumes" / "influxdb-data"


# --- брокер -------------------------------------------------------------------------------------------
def test_acl_template_parses_to_roles() -> None:
    acl = ls.parse_acl(ls.render_acl(ENV))
    assert set(acl) == {"plc", "telegraf", "operator", "monitor"}
    assert acl["plc"]["read"] == ["vodokanal/+/+/+/cmd/+"]
    assert "vodokanal/+/+/+/+" in acl["plc"]["write"]
    assert acl["telegraf"]["write"] == [] and acl["telegraf"]["read"] == ["vodokanal/#"]
    assert acl["operator"]["write"] == ["vodokanal/+/+/+/cmd/+"]
    assert acl["monitor"]["read"] == ["$SYS/#"]


def test_broker_config(layout: ls.Layout) -> None:
    path = ls.broker_config(ENV, layout, hasher=lambda p: f"hash({p})")
    config: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    plugins = config["plugins"]
    # вход только по паролю: плагина анонимного входа нет
    assert not any("Anonymous" in name for name in plugins)
    passwd = Path(plugins["amqtt.plugins.authentication.FileAuthPlugin"]["password_file"]).read_text(encoding="utf-8")
    assert "operator:hash(p3-secret)" in passwd.splitlines()
    acl = plugins["amqtt.plugins.topic_checking.TopicAccessControlListPlugin"]
    assert acl["publish_acl"]["operator"] == ["vodokanal/+/+/+/cmd/+"]
    assert acl["acl"]["telegraf"] == ["vodokanal/#"]
    assert config["listeners"]["default"]["bind"] == "127.0.0.1:1883"


def test_broker_rejects_placeholder_passwords(layout: ls.Layout) -> None:
    with pytest.raises(ls.StackError, match="не изменён"):
        ls.broker_config({**ENV, "MQTT_PLC_PASSWORD": "change-me"}, layout, hasher=str)


# --- Grafana ------------------------------------------------------------------------------------------
def test_grafana_provisioning_translated(layout: ls.Layout) -> None:
    out = ls.grafana_provisioning(ENV, layout)
    ds = yaml.safe_load((out / "datasources" / "influxdb.yml").read_text(encoding="utf-8"))["datasources"][0]
    assert ds["url"] == "http://127.0.0.1:8086" and ds["uid"] == "influx-kns"
    token_path = ds["secureJsonData"]["token"]
    assert token_path == "$__file{" + (layout.state / "volumes" / "influx-tokens" / "grafana.token").as_posix() + "}"
    prov = yaml.safe_load((out / "dashboards" / "kns.yml").read_text(encoding="utf-8"))["providers"][0]
    assert Path(prov["options"]["path"]) == (sc.REPO / "grafana" / "dashboards").resolve()


# --- скрипт PowerShell --------------------------------------------------------------------------------
def test_local_stack_ps1() -> None:
    raw = (sc.REPO / "tools_project" / "local_stack.ps1").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "UTF-8 с BOM для Windows PowerShell 5.1"
    text = raw.decode("utf-8-sig")
    assert "\r\n" in text and "\n" not in text.replace("\r\n", "")
    assert "&&" not in text and "??" not in text, "синтаксис PowerShell 7 недоступен в Windows PowerShell 5.1"
    match = re.search(r"ValidateSet\(([^)]*)\)", text)
    assert match and {t.strip().strip("'") for t in match.group(1).split(",")} == {
        "install",
        "start",
        "stop",
        "status",
        "logs",
    }
    for sub in ("broker-config", "grafana-provisioning", "influx-init", "launch", "wait", "wait-data", "stop"):
        assert f"'{sub}'" in text, sub


# --- проверка панелей ---------------------------------------------------------------------------------
def test_dashboard_variables_resolve() -> None:
    for path in sorted((sc.REPO / "grafana" / "dashboards").glob("*.json")):
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        values = cd.variable_values(dashboard)
        for panel in cd.panels(dashboard):
            for target in panel.get("targets", []):
                query = cd.substitute(target["query"], values)
                assert not re.search(r"\$\{?\w", query), f"{path.name} #{panel['id']}: {query}"


def test_priority_regex_is_all_priorities() -> None:
    dashboard = json.loads((sc.REPO / "grafana" / "dashboards" / "kns1-alarms.json").read_text(encoding="utf-8"))
    values = cd.variable_values(dashboard)
    assert cd.substitute("${priority:regex}", values) == "(Critical|High|Medium|Low)"


def test_may_be_empty_panels_exist() -> None:
    titles = set()
    for path in sorted((sc.REPO / "grafana" / "dashboards").glob("*.json")):
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        titles |= {(dashboard["uid"], p["title"]) for p in cd.panels(dashboard)}
    assert titles >= cd.MAY_BE_EMPTY


def test_frame_rows_and_markdown() -> None:
    assert cd.frame_rows({"frames": [{"data": {"values": [[1, 2], [3, 4]]}}, {"data": {"values": []}}]}) == 2
    results = [
        cd.PanelResult("kns1-overview", 4, "Уровень LT101", "stat", 1, ""),
        cd.PanelResult("kns1-overview", 26, "Активные тревоги", "table", 0, ""),
        cd.PanelResult("kns1-pumps", 7, "Наработка по суткам, ч", "timeseries", 0, "A: unknown time zone"),
    ]
    assert [r.ok for r in results] == [True, True, False]
    md = cd.markdown(results)
    assert "без данных или с ошибкой: 1" in md and "пусто — всё в норме" in md and "ошибка: A: unknown" in md
