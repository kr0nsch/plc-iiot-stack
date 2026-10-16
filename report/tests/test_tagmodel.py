"""Модель тегов флагмана: соответствие вывода iolistgen и узлов OPC UA."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest

from kns_report.cli import required_tags
from kns_report.config import ReportConfig
from kns_report.opcua_source import node_id
from kns_report.tagmodel import AlarmDef, TagInfo, alarm_devices, device_title


def test_report_tags_exist_in_flagship_model(
    cfg: ReportConfig, tags: dict[str, TagInfo], alarms: list[AlarmDef]
) -> None:
    wanted = required_tags(cfg.station, alarms)
    assert [t for t in wanted if t not in tags] == []
    assert tags["LT101.Value"].plc_path == "Application.GVL_Devices.fbLT101.stSts.rValue_eu"
    assert tags["LT101.Value"].units == "м"
    assert tags["FT202.Value"].units == "м³/ч"
    assert tags["P101.RunTime"].plc_path.endswith("fbP101.stSts.rRunTime_h")
    assert tags["P101.Starts"].data_type == "UDINT"
    assert tags["P101.AlmActive"].data_type == "WORD"


def test_node_id_template_reproduces_scada_csv(cfg: ReportConfig, tags: dict[str, TagInfo]) -> None:
    mismatched = [
        info.tag for info in tags.values() if node_id(cfg.opcua, info, cfg.opcua.ns_index) != info.opcua_node_id
    ]
    assert mismatched == []


def test_level_limits_from_signal_list(tags: dict[str, TagInfo]) -> None:
    level = tags["LT101.Value"]
    assert (level.alarm_hh, level.alarm_h, level.alarm_l, level.alarm_ll) == (4.0, 3.5, 0.8, 0.5)


def test_alarm_ids_follow_dev_no_rule(alarms: list[AlarmDef]) -> None:
    by_code = {a.code: a for a in alarms}
    assert by_code["P101.FTS"].id == 110
    assert by_code["LT101.HH"].slot == 0
    assert by_code["LT101.H"].slot == 1
    assert by_code["ZS404.ALM"].priority == "Low"
    assert all(a.id % 10 == a.slot for a in alarms)
    assert len({a.code for a in alarms}) == len(alarms)


def test_alarm_devices_and_titles(alarms: list[AlarmDef], tags: dict[str, TagInfo]) -> None:
    devices = alarm_devices(alarms)
    assert devices[:3] == ["P101", "P102", "P103"]
    assert "LT101" in devices and "YS405" in devices
    assert device_title(tags, "P102") == "Насос Н2"
    assert device_title(tags, "LT101") == "LT101"


@pytest.mark.parametrize("name", ["scada_tags.csv", "scada_alarms.csv"])
def test_bundled_copy_matches_schema_source(name: str) -> None:
    """Встроенная копия вывода iolistgen совпадает с schema/source/ репозитория (если он рядом)."""
    source = Path(__file__).resolve().parents[2] / "schema" / "source" / name
    if not source.exists():
        pytest.skip("schema/source/ нет: пакет проверяется вне репозитория")
    bundled = resources.files("kns_report").joinpath("data", name).read_bytes()
    assert bundled == source.read_bytes(), f"обновите report/kns_report/data/{name} из schema/source/"
