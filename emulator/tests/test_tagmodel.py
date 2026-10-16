"""Модель тегов: эмулятор зеркалит перечень флагмана, копии данных совпадают со schema/."""

from __future__ import annotations

from collections import Counter

import pytest
from conftest import SCHEMA_DIR

from iiot_emulator import tagmodel
from iiot_emulator.emulator import EmulatorConfig, KnsEmulator
from iiot_emulator.schema import command_whitelist, telemetry_catalog


def test_tag_list_loaded() -> None:
    tags = tagmodel.load_tags()
    assert len(tags) == 814
    assert len(tagmodel.load_alarms()) == 75
    assert len(tagmodel.devices()) == 29
    assert Counter(t.data_type for t in tags) == {
        "WORD": 298,
        "BOOL": 224,
        "INT": 158,
        "UINT": 69,
        "REAL": 53,
        "UDINT": 12,
    }


def test_node_ids_are_codesys_style() -> None:
    for t in tagmodel.load_tags():
        assert tagmodel.node_id_for(t) == t.opcua_node_id
        assert t.opcua_node_id.startswith("ns=4;s=|var|CODESYS Control Win V3.Application.")
        if t.writable:
            assert ".GVL_Hmi." in t.plc_path, t.tag


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
