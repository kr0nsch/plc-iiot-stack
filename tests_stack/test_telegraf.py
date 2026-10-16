"""Telegraf пишет только то, что объявлено в docs/data_schema.md (раздел 7), и слушает топики topics.json."""

from __future__ import annotations

import json
import re
import tomllib
from typing import Any

import pytest
import yaml

import stack_catalog as sc
from stack_model import TYPE_ALIASES, MeasurementModel, env_refs, load_influx_model

TELEGRAF = sc.REPO / "telegraf"
# measurement → класс сообщений schema/topics.json и файл схемы
MEASUREMENT_CLASS = {
    "telemetry": "telemetry",
    "alarm": "alarm",
    "command": "command",
    "command_ack": "command_ack",
    "node_status": "status",
}


@pytest.fixture(scope="module")
def conf() -> dict[str, Any]:
    return tomllib.loads((TELEGRAF / "telegraf.conf").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def opcua() -> dict[str, Any]:
    data: dict[str, Any] = tomllib.loads((TELEGRAF / "telegraf.d" / "opcua.conf").read_text(encoding="utf-8"))
    plugins: list[dict[str, Any]] = data["inputs"]["opcua"]
    assert len(plugins) == 1
    return plugins[0]


@pytest.fixture(scope="module")
def model() -> dict[str, MeasurementModel]:
    return load_influx_model()


def mqtt_inputs(conf: dict[str, Any]) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = conf["inputs"]["mqtt_consumer"]
    return inputs


def test_one_mqtt_input_per_message_class(conf: dict[str, Any]) -> None:
    names = sorted(i["json_v2"][0]["measurement_name"] for i in mqtt_inputs(conf))
    assert names == sorted(MEASUREMENT_CLASS)
    assert len({i["client_id"] for i in mqtt_inputs(conf)}) == len(names), "client_id должны различаться"


def test_mqtt_inputs_write_only_declared_names(conf: dict[str, Any], model: dict[str, MeasurementModel]) -> None:
    for inp in mqtt_inputs(conf):
        j = inp["json_v2"][0]
        meas = model[j["measurement_name"]]
        tags = {t.get("rename", t["path"]) for t in j.get("tag", [])} - {"schema_version"}
        assert tags <= meas.tags, (meas.name, tags - meas.tags)
        for f in j["field"]:
            name = f.get("rename", f["path"])
            assert name in meas.fields, (meas.name, name)
            assert TYPE_ALIASES[f["type"]] == meas.fields[name], (meas.name, name)
        parsing = inp["topic_parsing"][0]
        topic_tags = {t for t in parsing["tags"].split("/") if t != "_"}
        assert topic_tags <= meas.tags, (meas.name, topic_tags - meas.tags)
        assert set(inp.get("tags", {})) <= meas.tags


def test_mqtt_inputs_follow_message_schemas(conf: dict[str, Any]) -> None:
    """Пути json_v2 есть в схеме класса; обязательные для Telegraf поля обязательны и в схеме."""
    for inp in mqtt_inputs(conf):
        j = inp["json_v2"][0]
        schema = sc.load_schema(MEASUREMENT_CLASS[j["measurement_name"]])
        props, required = schema["properties"], set(schema["required"])
        if j["measurement_name"] == "node_status":
            # время приёма: ts завещания — время подключения (data_schema.md, 7.1)
            assert "timestamp_path" not in j
        else:
            assert j["timestamp_path"] == "ts" and j["timestamp_format"] == "unix_ms"
        for item in [*j.get("tag", []), *j["field"]]:
            assert item["path"] in props, (j["measurement_name"], item["path"])
            if not item.get("optional", False):
                assert item["path"] in required, (j["measurement_name"], item["path"])


def test_mqtt_inputs_subscribe_to_class_filters(conf: dict[str, Any]) -> None:
    classes = sc.load_topics()["classes"]
    root = sc.station()["site"]
    for inp in mqtt_inputs(conf):
        cls = classes[MEASUREMENT_CLASS[inp["json_v2"][0]["measurement_name"]]]
        topics = [t.replace("${MQTT_TOPIC_ROOT}", root) for t in inp["topics"]]
        assert topics == [cls["filter"]]
        parsing = inp["topic_parsing"][0]
        levels = cls["filter"].split("/")
        assert len(parsing["topic"].split("/")) == len(levels) == len(parsing["tags"].split("/"))
        assert inp["qos"] == cls["qos"] == 1 and inp["persistent_session"] is True


def test_mqtt_inputs_accept_only_schema_major_1(conf: dict[str, Any]) -> None:
    for inp in mqtt_inputs(conf):
        assert inp["tagpass"] == {"schema_version": ["1.*"]}
        assert "schema_version" in inp["tagexclude"]
        assert inp["topic_tag"] == "", "тег topic дублирует site/area/unit/device"
        assert inp["data_format"] == "json_v2"


def test_opcua_input_matches_catalog(opcua: dict[str, Any], model: dict[str, MeasurementModel]) -> None:
    meas = model["telemetry"]
    assert opcua["name"] == "telemetry" and opcua["tags"] == {"source": "opcua"}
    assert opcua["tagexclude"] == ["id"]
    group = opcua["group"][0]
    assert group["name"] == "telemetry"
    assert set(group["default_tags"]) <= meas.tags
    st = sc.station()
    assert group["default_tags"] == {"site": st["site"], "area": st["area"], "unit": st["unit"]}
    expected = {(m.device, m.metric): m.plc_path for m in sc.load_catalog() if m.plc_path}
    seen = {}
    for node in group["nodes"]:
        assert node["name"] in meas.fields
        assert set(node["default_tags"]) == {"device", "metric"}
        key = (node["default_tags"]["device"], node["default_tags"]["metric"])
        seen[key] = node["identifier"].removeprefix("${OPCUA_ID_PREFIX}")
    assert seen == expected


def test_opcua_client_certificate_is_persistent(opcua: dict[str, Any]) -> None:
    """Сертификат клиента OPC UA: пути из окружения, по умолчанию — именованный том (не слой контейнера).

    Без путей Telegraf при защищённой политике создаёт новый самоподписанный сертификат при каждом старте,
    и сервер CODESYS пришлось бы заново доверять ему после каждого пересоздания контейнера.
    """
    assert opcua["certificate"] == "${OPCUA_CERTIFICATE}"
    assert opcua["private_key"] == "${OPCUA_PRIVATE_KEY}"
    compose = yaml.safe_load((sc.REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    telegraf = compose["services"]["telegraf"]
    assert "telegraf-pki:/var/lib/telegraf/pki" in telegraf["volumes"]
    assert "telegraf-pki" in compose["volumes"]
    entry = (TELEGRAF / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert "PKI_DIR=/var/lib/telegraf/pki" in entry
    assert 'OPCUA_CERTIFICATE="${OPCUA_CERTIFICATE:-$PKI_DIR/cert.pem}"' in entry
    assert 'chown telegraf:telegraf "$PKI_DIR"' in entry


def test_opcua_node_ids_match_iolistgen() -> None:
    """С префиксом и пространством имён по умолчанию узел совпадает с opcua_node_id перечня."""
    tags = {t.plc_path: t.opcua_node_id for t in sc.load_scada_tags()}
    compose = yaml.safe_load((sc.REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    env = compose["services"]["telegraf"]["environment"]
    prefix = env["OPCUA_ID_PREFIX"].split(":-", 1)[1].rstrip("}")
    ns = env["OPCUA_NAMESPACE"].split(":-", 1)[1].rstrip("}")
    for m in sc.load_catalog():
        if m.plc_path:
            assert tags[m.plc_path] == f"ns={ns};s={prefix}{m.plc_path}"


def test_processors_are_consistent(conf: dict[str, Any], model: dict[str, MeasurementModel]) -> None:
    proc = conf["processors"]
    conv = proc["converter"][0]
    assert conv["namepass"] == ["telemetry"] and conv["fields"]["float"] == ["value"]
    assert model["telemetry"].fields["value"] == "float"
    rename = proc["rename"][0]["replace"][0]
    assert rename["field"] == "Quality" and rename["dest"] in model["telemetry"].fields
    lookup = proc["lookup"][0]
    assert lookup["namepass"] == ["alarm"] and lookup["format"] == "json"
    assert lookup["key"] == '{{.Tag "code"}}' and "code" in model["alarm"].tags
    local = TELEGRAF / "lookup" / lookup["files"][0].rsplit("/", 1)[1]
    added = {tag for entry in json.loads(local.read_text(encoding="utf-8")).values() for tag in entry}
    assert added <= model["alarm"].tags
    assert len({p[0]["order"] for p in proc.values()}) == len(proc)


def test_outputs_use_least_privilege_token(conf: dict[str, Any]) -> None:
    out = conf["outputs"]["influxdb_v2"][0]
    assert out["token"] == "${INFLUX_TOKEN}"
    assert out["bucket"] == "${INFLUX_BUCKET}"
    assert out["namedrop"] == ["internal*"]
    health = conf["outputs"]["health"][0]
    assert health["namepass"] == ["internal_write"]
    assert health["compares"][0]["field"] == "buffer_size"
    assert health["compares"][0]["lt"] <= conf["agent"]["metric_buffer_limit"] / 2


def test_environment_variables_are_provided_by_compose() -> None:
    compose = yaml.safe_load((sc.REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    provided = set(compose["services"]["telegraf"]["environment"]) | {"INFLUX_TOKEN"}  # INFLUX_TOKEN — entrypoint
    texts = [(TELEGRAF / "telegraf.conf").read_text(encoding="utf-8")]
    texts.append((TELEGRAF / "telegraf.d" / "opcua.conf").read_text(encoding="utf-8"))
    used = set().union(*(env_refs(t) for t in texts))
    # ${VAR:-умолчание} — значение для контейнера в самом конфиге; переменную задаёт только локальный
    # стенд без Docker (tools_project/local_stack.py)
    with_default = {m for t in texts for m in re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*):-", t)}
    assert used - with_default <= provided, used - with_default - provided
    assert with_default == {"TELEGRAF_LOOKUP_DIR", "TELEGRAF_HEALTH_ADDRESS"}


def test_lookup_path_is_mounted() -> None:
    compose = yaml.safe_load((sc.REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    mounts = compose["services"]["telegraf"]["volumes"]
    assert "./telegraf/lookup:/etc/telegraf/lookup:ro" in mounts
    assert "./telegraf/telegraf.d:/etc/telegraf/telegraf.d:ro" in mounts
