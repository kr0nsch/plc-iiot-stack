"""Дашборды Grafana: провиженинг, запросы Flux против модели хранения и каталога, стиль ISA-101."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

import gen_config
import stack_catalog as sc
from stack_model import FLUX_BUILTIN_COLUMNS, MeasurementModel, flux_refs, load_influx_model

GRAFANA = sc.REPO / "grafana"
DASHBOARDS = sorted((GRAFANA / "dashboards").glob("*.json"))
REQUIRED_TITLES = {"КНС-1: обзор станции", "Насосы: моточасы и пуски", "Тревоги за период"}


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def panels(board: dict[str, Any]) -> list[dict[str, Any]]:
    return [p for p in board["panels"] if p["type"] != "row"]


def targets() -> list[tuple[str, str, str]]:
    out = []
    for path in DASHBOARDS:
        board = load(path)
        for p in panels(board):
            for t in p["targets"]:
                out.append((board["uid"], p["title"], t["query"]))
    return out


@pytest.fixture(scope="module")
def model() -> dict[str, MeasurementModel]:
    return load_influx_model()


@pytest.fixture(scope="module")
def datasource() -> dict[str, Any]:
    data = yaml.safe_load((GRAFANA / "provisioning" / "datasources" / "influxdb.yml").read_text(encoding="utf-8"))
    sources: list[dict[str, Any]] = data["datasources"]
    assert len(sources) == 1
    return sources[0]


def test_datasource_is_flux_with_file_token(datasource: dict[str, Any]) -> None:
    assert datasource["type"] == "influxdb" and datasource["jsonData"]["version"] == "Flux"
    assert datasource["url"] == "http://influxdb:8086"
    assert datasource["jsonData"]["defaultBucket"] == "${INFLUX_BUCKET}"
    assert datasource["secureJsonData"]["token"] == "$__file{/run/influx-tokens/grafana.token}"
    assert datasource["editable"] is False


def test_dashboard_provider_matches_mount() -> None:
    prov = yaml.safe_load((GRAFANA / "provisioning" / "dashboards" / "kns.yml").read_text(encoding="utf-8"))
    path = prov["providers"][0]["options"]["path"]
    compose = yaml.safe_load((sc.REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    grafana = compose["services"]["grafana"]
    assert f"./grafana/dashboards:{path}:ro" in grafana["volumes"]
    home = grafana["environment"]["GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH"]
    assert home.startswith(path + "/") and (GRAFANA / "dashboards" / Path(home).name).exists()


def test_three_required_dashboards() -> None:
    boards = [load(p) for p in DASHBOARDS]
    assert {b["title"] for b in boards} == REQUIRED_TITLES
    assert len({b["uid"] for b in boards}) == len(boards)
    for b in boards:
        assert b["id"] is None and "kns1" in b["tags"]


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_panels_use_provisioned_datasource_and_fit_grid(path: Path, datasource: dict[str, Any]) -> None:
    board = load(path)
    ids = [p["id"] for p in board["panels"]]
    assert len(ids) == len(set(ids))
    cells: set[tuple[int, int]] = set()
    for p in board["panels"]:
        g = p["gridPos"]
        assert g["x"] >= 0 and g["x"] + g["w"] <= 24, p["title"]
        own = {(x, y) for x in range(g["x"], g["x"] + g["w"]) for y in range(g["y"], g["y"] + g["h"])}
        assert not own & cells, f"панель «{p['title']}» перекрывает другую"
        cells |= own
        if p["type"] == "row":
            continue
        assert p["datasource"]["uid"] == datasource["uid"]
        assert all(t["datasource"]["uid"] == datasource["uid"] for t in p["targets"])


@pytest.mark.parametrize(("uid", "title", "query"), targets(), ids=lambda v: v if len(v) < 40 else "")
def test_flux_query_references_declared_names(
    uid: str, title: str, query: str, model: dict[str, MeasurementModel]
) -> None:
    refs = flux_refs(query)
    assert refs.measurements, f"{uid} / {title}: в запросе нет фильтра по _measurement"
    assert refs.measurements <= set(model), refs.measurements - set(model)
    tags = set().union(*(model[m].tags for m in refs.measurements))
    fields = set().union(*(model[m].fields for m in refs.measurements))
    assert query.startswith(("from(bucket: v.defaultBucket)", "import ")), "бакет — из источника данных"
    assert "from(bucket: v.defaultBucket)" in query
    assert refs.fields <= fields, refs.fields - fields
    assert refs.columns <= tags | FLUX_BUILTIN_COLUMNS, refs.columns - tags - FLUX_BUILTIN_COLUMNS
    allowed_columns = tags | set(fields) | FLUX_BUILTIN_COLUMNS | refs.renamed_to
    assert refs.listed_columns <= allowed_columns, refs.listed_columns - allowed_columns
    # Значения строковых полей — из перечислений схем сообщений
    enums = {
        "alarm": sc.load_schema("alarm")["properties"]["state"]["enum"]
        + sc.load_schema("alarm")["properties"]["reason"]["enum"],
        "node_status": sc.load_schema("status")["properties"]["state"]["enum"],
    }
    for value in refs.eq.get("_value", set()):
        allowed = set().union(*(set(enums.get(m, [])) for m in refs.measurements))
        assert value in allowed, f"{title}: значение {value!r} не из схемы"


@pytest.mark.parametrize(("uid", "title", "query"), targets(), ids=lambda v: v if len(v) < 40 else "")
def test_flux_telemetry_queries_use_catalog_metrics(uid: str, title: str, query: str) -> None:
    refs = flux_refs(query)
    if "telemetry" not in refs.measurements:
        return
    catalog = sc.load_catalog()
    pairs = {(m.device, m.metric) for m in catalog}
    metrics = refs.eq.get("metric", set())
    assert metrics, f"{title}: запрос телеметрии без фильтра по metric"
    assert refs.eq.get("source") == {"${source}"}, f"{title}: путь данных — переменная source"
    devices = refs.eq.get("device", set())
    for metric in metrics:
        assert metric in {m.metric for m in catalog}, metric
        for device in devices:
            assert (device, metric) in pairs, (device, metric)


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_template_variables_are_declared(path: Path) -> None:
    board = load(path)
    declared = {v["name"] for v in board["templating"]["list"]}
    used: set[str] = set()
    for p in panels(board):
        for t in p["targets"]:
            used |= flux_refs(t["query"]).variables
    assert used <= declared, used - declared
    assert declared <= used, f"лишние переменные: {declared - used}"


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_isa101_palette(path: Path) -> None:
    """Цвет — для отклонений и для различения насосов: без многоцветных палитр Grafana, цвета заданы явно."""
    text = path.read_text(encoding="utf-8")
    assert "palette-classic" not in text and "continuous-" not in text
    for p in panels(load(path)):
        mode = p["fieldConfig"]["defaults"].get("color", {}).get("mode")
        assert mode in ("fixed", "thresholds"), (p["title"], mode)


def _override_colors(panel: dict[str, Any]) -> dict[str, str]:
    """Цвета рядов из переопределений: устройство (из регулярного выражения сопоставления) → цвет."""
    out: dict[str, str] = {}
    devices = (*gen_config.PUMPS, *gen_config.PUMP_CURRENT)
    for o in panel["fieldConfig"]["overrides"]:
        for prop in o["properties"]:
            if prop["id"] == "color":
                assert o["matcher"]["id"] == "byRegexp", panel["title"]
                (device,) = (d for d in devices if d in o["matcher"]["options"])
                out[device] = prop["value"]["fixedColor"]
    return out


def test_pump_colors_are_distinct_and_not_status_colors() -> None:
    colors = set(gen_config.PUMP_COLORS.values())
    assert len(colors) == len(gen_config.PUMPS)
    status = {*gen_config.C_PRIO.values(), *gen_config.C_NE107.values(), gen_config.C_NOT_AUTO, gen_config.C_NORMAL}
    assert not {c.upper() for c in colors} & {c.upper() for c in status}


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_pump_series_use_pump_colors(path: Path) -> None:
    """Насос — один цвет во всех дашбордах: в каждом графике, столбцах и шкалах по насосам (и по их токам)."""
    expected = {**gen_config.PUMP_COLORS, **gen_config.CURRENT_COLORS}
    for p in panels(load(path)):
        if p["type"] not in ("timeseries", "barchart", "bargauge"):
            continue
        devices = flux_refs(p["targets"][0]["query"]).eq.get("device", set())
        if not devices <= set(expected) or len(devices) < 2:
            continue
        assert _override_colors(p) == {d: expected[d] for d in devices}, p["title"]


def test_priority_bars_are_russian_and_sorted_by_severity() -> None:
    board = load(GRAFANA / "dashboards" / "kns1-alarms.json")
    panel = next(p for p in panels(board) if p["title"] == "Срабатывания по приоритетам")
    query = panel["targets"][0]["query"]
    ranks = re.findall(r'r\.priority == "(\w+)" then (\d)', query)
    assert ranks == [("Critical", "1"), ("High", "2"), ("Medium", "3")]
    assert query.endswith('|> sort(columns: ["rank"])\n  |> keep(columns: ["priority", "_value"])\n')
    # каждый приоритет фильтра — строкой, и без срабатываний (нули из array.from)
    assert re.findall(r'\{priority: "(\w+)", _value: 0\}', query) == list(gen_config.PRIORITY_RU)
    # строка на приоритет → поле на приоритет в том же порядке; подпись и цвет — по имени поля
    assert [t["id"] for t in panel["transformations"]] == ["rowsToFields"]
    names = {
        o["matcher"]["options"]: {prop["id"]: prop["value"] for prop in o["properties"]}
        for o in panel["fieldConfig"]["overrides"]
    }
    assert {k: v["displayName"] for k, v in names.items()} == gen_config.PRIORITY_RU
    assert {k: v["color"]["fixedColor"] for k, v in names.items()} == gen_config.C_PRIO
    var = next(v for v in board["templating"]["list"] if v["name"] == "priority")
    assert var["query"] == "Критический : Critical,Высокий : High,Средний : Medium,Низкий : Low"


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_tables_keep_column_order_and_wrap_alarm_text(path: Path) -> None:
    """Порядок столбцов — заданный; текст тревоги переносится; перенос — у одного столбца таблицы."""
    for p in panels(load(path)):
        if p["type"] != "table":
            continue
        names = [o["matcher"]["options"] for o in p["fieldConfig"]["overrides"]]
        organize = next(t for t in p.get("transformations", []) if t["id"] == "organize")
        assert list(organize["options"]["indexByName"]) == names, p["title"]
        wrapped = [
            o["matcher"]["options"]
            for o in p["fieldConfig"]["overrides"]
            if {"id": "custom.wrapText", "value": True} in o["properties"]
        ]
        assert len(wrapped) == 1, (p["title"], wrapped)
        assert "text" not in names or wrapped == ["text"], p["title"]


# Заголовок панели stat не должен обрезаться при ширине окна 1280 px: колонка сетки ≈ 52 px, на меню
# и поля панели уходит ≈ 74 px, на значок описания — 32 px; символ Inter 14 px — в среднем до 8.5 px
GRID_COLUMN_PX = 52.3
TITLE_RESERVE_PX = 74
DESCRIPTION_ICON_PX = 32
TITLE_CHAR_PX = 8.5


@pytest.mark.parametrize("path", DASHBOARDS, ids=lambda p: p.stem)
def test_stat_titles_fit_at_1280px(path: Path) -> None:
    for p in panels(load(path)):
        if p["type"] != "stat":
            continue
        width = p["gridPos"]["w"] * GRID_COLUMN_PX - TITLE_RESERVE_PX
        width -= DESCRIPTION_ICON_PX if p.get("description") else 0
        assert len(p["title"]) * TITLE_CHAR_PX <= width, f"«{p['title']}» не помещается в {width:.0f} px"


def _thresholds(board: dict[str, Any], title_prefix: str) -> list[float]:
    panel = next(p for p in panels(board) if p["title"].startswith(title_prefix))
    steps = panel["fieldConfig"]["defaults"]["thresholds"]["steps"]
    return [s["value"] for s in steps if s["value"] is not None]


def test_level_bands_follow_alarm_setpoints() -> None:
    board = load(GRAFANA / "dashboards" / "kns1-overview.json")
    limits = sc.alarm_limits("LT101")
    expected = sorted(v for v, _ in limits.values())
    assert _thresholds(board, "Уровень в резервуаре LT101") == expected
    assert _thresholds(board, "Давление в коллекторе PT201") == sorted(v for v, _ in sc.alarm_limits("PT201").values())
    assert expected == [0.5, 0.8, 3.5, 4.0]


def test_queries_have_no_hardcoded_bucket_or_secrets() -> None:
    for _uid, title, query in targets():
        assert not re.search(r"from\(bucket:\s*\"", query), title
        assert "token" not in query.lower(), title
