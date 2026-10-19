"""Модель тегов: эмулятор зеркалит теги флагмана (устройства, станция, LIC101), копии совпадают со schema/."""

from __future__ import annotations

from collections import Counter

import pytest
from conftest import SCHEMA_DIR

from iiot_emulator import tagmodel
from iiot_emulator.emulator import EmulatorConfig, KnsEmulator
from iiot_emulator.schema import command_whitelist, telemetry_catalog


def test_tag_list_loaded() -> None:
    tags = tagmodel.load_tags()
    assert len(tags) == 914  # 843 тега устройств (iolistgen 0.2.0) и 71 тег станции и LIC101
    assert len(tagmodel.load_alarms()) == 88  # 75 тревог устройств и 13 тревог станции KNS1.*
    assert len(tagmodel.devices()) == 29
    assert Counter(t.data_type for t in tags) == {
        "WORD": 346,
        "BOOL": 238,
        "INT": 170,
        "UINT": 76,
        "REAL": 67,
        "UDINT": 17,
    }
    station = [a for a in tagmodel.load_alarms() if a.device == "KNS1"]
    assert [a.bit for a in station] == [a.slot - 1 for a in station] == list(range(13))
    assert all(a.bit == a.slot for a in tagmodel.load_alarms() if a.device != "KNS1")


def test_node_ids_are_codesys_style() -> None:
    for t in tagmodel.load_tags():
        assert tagmodel.node_id_for(t) == t.opcua_node_id
        assert t.opcua_node_id.startswith("ns=4;s=|var|CODESYS Control Win V3.Application.")
        if t.writable:  # SCADA пишет только команды и задания (правила символов флагмана)
            assert t.plc_path.startswith(
                (
                    "Application.GVL_Hmi.",
                    "Application.GVL_Station.stStationCmd.",
                    "Application.GVL_Station.stLIC101Cmd.",
                )
            ), t.tag


def test_emulator_image_covers_every_tag() -> None:
    emu = KnsEmulator(EmulatorConfig(auto_faults=False))
    image = emu.image()
    assert set(image) == {t.tag for t in tagmodel.load_tags()}
    for t in tagmodel.load_tags():
        v = image[t.tag]
        if t.data_type == "BOOL":
            assert isinstance(v, bool), t.tag
        elif t.data_type == "REAL":
            assert isinstance(v, float), t.tag
        else:
            assert isinstance(v, int) and not isinstance(v, bool), t.tag
            lo, hi = tagmodel.IEC_INT_RANGES[t.data_type]
            assert lo <= v <= hi, t.tag


def test_catalog_and_whitelist_refer_to_known_tags() -> None:
    names = {t.tag for t in tagmodel.load_tags()}
    for m in telemetry_catalog():
        assert not m.scada_tag or m.scada_tag in names, m
    for e in command_whitelist().values():
        assert e.scada_tag in names and tagmodel.tags_by_name()[e.scada_tag].writable, e


@pytest.mark.parametrize(
    ("packaged", "repo"),
    [
        ("scada_tags.csv", "source/scada_tags.csv"),
        ("scada_alarms.csv", "source/scada_alarms.csv"),
        ("station_tags.csv", "source/station_tags.csv"),
        ("station_alarms.csv", "source/station_alarms.csv"),
        ("telemetry_catalog.csv", "telemetry_catalog.csv"),
        ("command_whitelist.csv", "command_whitelist.csv"),
        ("topics.json", "topics.json"),
    ],
)
def test_schema_copies_match_repo(packaged: str, repo: str) -> None:
    """Копии в iiot_emulator/data/ совпадают с контрактом schema/ (образ Docker собирается без него)."""
    from importlib import resources

    src = SCHEMA_DIR / repo
    if not src.is_file():
        pytest.skip(f"нет {src}")
    ours = resources.files("iiot_emulator").joinpath("data", packaged).read_bytes()
    assert ours == src.read_bytes(), f"скопируйте schema/{repo} в emulator/iiot_emulator/data/{packaged}"
