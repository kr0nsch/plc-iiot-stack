"""config.json репозитория (tools/codesys/config.json) — проверки уровня схемы.

Остальные тесты инструментов берут настройки из эталона tools/tests/fixtures/config_template.json
(копия config.json шаблона): у репозитория-проекта config.json свой — библиотеки, задачи режимов,
библиотека репозитория (раздел library), — и тесты шаблона от этого не зависят. Здесь проверяется
только то, что cds.py нужно от любого config.json:

- JSON без абсолютных путей пользователя;
- те же разделы и ключи настроек, что у эталона (кроме разделов, которые проект наполняет сам:
  modes и libraries). Ключ, добавленный в config.json шаблона, добавляется и в эталон — иначе этот
  тест упадёт в самом шаблоне; проекту, обновившему tools/, тест подскажет, какого ключа не хватает;
- режимы, задачи и описания библиотек полные, все ссылки на библиотеки описаны и разрешаются,
  раздел library проходит проверки cds.py; в тестовом режиме есть библиотека тестового фреймворка.

Те же проверки (кроме сравнения с самим собой) выполняются и для эталона.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from cdshost import cli
from conftest import CONFIG_TEMPLATE, LIVE_CONFIG, template_config

# Разделы, которые проект наполняет своими записями: задачи и библиотеки режимов, описания библиотек
OPEN_SECTIONS = ("modes", "libraries")
MODES = ("normal", "test")
MODE_KEYS = {"tasks", "libraries"}
TASK_KEYS = {"name", "interval_ms", "pous", "priority"}
# Ключи описания библиотеки (Settings.library_spec); install_from, build_from_repo — пути
LIBRARY_SPEC_KEYS = {
    "label",
    "namespace",
    "title",
    "title_contains",
    "company",
    "version",
    "placeholder",
    "qualified_only",
    "install_from",
    "build_from_repo",
}

CONFIGS = [pytest.param(LIVE_CONFIG, id="config.json"), pytest.param(CONFIG_TEMPLATE, id="эталон")]


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path}: ожидался объект JSON"
    return data


def is_value_node(node: Any) -> bool:
    """Значение настройки: {"env": ..., "default": ...} — как Settings._raw."""
    return isinstance(node, Mapping) and ("env" in node or "default" in node)


def shape(node: Any, prefix: str = "") -> set[str]:
    """Пути ключей настроек (через точку). Лист — не объект или значение {"env", "default"};
    ключи на '_' (описания) не учитываются, открытые разделы — только по имени."""
    paths: set[str] = set()
    if not isinstance(node, Mapping) or is_value_node(node):
        return paths
    for key, value in node.items():
        if str(key).startswith("_"):
            continue
        path = f"{prefix}{key}"
        paths.add(path)
        if path not in OPEN_SECTIONS:
            paths |= shape(value, path + ".")
    return paths


def settings(data: dict[str, Any], root: Path) -> cli.Settings:
    environ = {"USERPROFILE": str(root / "home"), "HOME": str(root / "home"), "LOCALAPPDATA": str(root / "lad")}
    return cli.Settings(data, root, cli.make_getenv(environ, registry=False))


def test_config_is_valid_json_without_user_paths() -> None:
    text = LIVE_CONFIG.read_text(encoding="utf-8")
    load(LIVE_CONFIG)
    user = os.environ.get("USERNAME") or os.environ.get("USER")
    assert not user or f"/{user.lower()}/" not in text.lower().replace("\\\\", "/")
    assert "C:\\\\Users" not in text and "C:/Users" not in text


def test_config_has_template_shape() -> None:
    """Разделы и ключи настроек — как у эталона; значения, задачи и библиотеки — свои у проекта."""
    live = shape(load(LIVE_CONFIG))
    template = shape(template_config())
    missing = sorted(template - live)
    extra = sorted(live - template)
    assert not missing and not extra, (
        f"config.json отличается от эталона tools/tests/fixtures/config_template.json набором ключей: "
        f"нет {missing}, лишние {extra}. В проекте — добавьте недостающие ключи из config.json шаблона; "
        "в шаблоне — обновите эталон вместе с config.json"
    )


@pytest.mark.parametrize("path", CONFIGS)
def test_modes_and_libraries_are_complete(path: Path, tmp_path: Path) -> None:
    data = load(path)
    modes = data["modes"]
    assert set(MODES) <= set(modes), f"нужны режимы {MODES}"
    libraries = {k: v for k, v in data["libraries"].items() if not k.startswith("_")}
    for key, spec in libraries.items():
        assert isinstance(spec, dict), f"libraries.{key}"
        unknown = sorted(set(spec) - LIBRARY_SPEC_KEYS - {"_doc"})
        assert not unknown, f"libraries.{key}: неизвестные ключи {unknown}"
    for mode, cfg in modes.items():
        assert set(cfg) <= MODE_KEYS, f"modes.{mode}: неизвестные ключи {set(cfg) - MODE_KEYS}"
        names: set[str] = set()
        for task in cfg.get("tasks", []):
            assert set(task) <= TASK_KEYS, f"modes.{mode}: задача {task}"
            assert isinstance(task["name"], str) and task["name"], f"modes.{mode}: имя задачи"
            assert task["name"].lower() not in names, f"modes.{mode}: задача {task['name']} дважды"
            names.add(task["name"].lower())
            assert float(task["interval_ms"]) > 0, f"modes.{mode}.{task['name']}: interval_ms"
            assert task["pous"] and all(isinstance(p, str) and p for p in task["pous"]), f"{task['name']}: pous"
        for key in cfg.get("libraries", []):
            assert key in libraries, f"modes.{mode}.libraries: {key} не описана в libraries"
    for key in data["library"].get("libraries", []):
        assert key in libraries, f"library.libraries: {key} не описана в libraries"
    s = settings(data, tmp_path / "repo")
    for mode in modes:
        s.mode_config(mode)  # описания библиотек разрешаются (версии, идентичность, пути)
    lib = s.library_config()
    assert all(isinstance(x, str) for x in lib["exclude"])
    # run_tests.py читает результаты из tests.runner: его пространство имён — у библиотеки режима test
    runner_ns = str(s.value("tests.runner")).split(".")[0].lower()
    namespaces = {str(x.get("namespace") or "").lower() for x in s.mode_config("test")["libraries"]}
    assert runner_ns in namespaces, f"tests.runner {runner_ns}: нет библиотеки с таким namespace в режиме test"
    s.device()
    for dotted in ("codesys.timeout_s", "tests.timeout_s", "lock.timeout_s", "runtime.port"):
        assert s.number(dotted) > 0, dotted


def test_shape_ignores_values_and_open_sections() -> None:
    a = {"_doc": "x", "codesys": {"timeout_s": {"env": "T", "default": 1}}, "modes": {"normal": {"tasks": []}}}
    b = {"codesys": {"timeout_s": 900}, "modes": {"x": {}}, "libraries": {"pl": {"title": "pl"}}}
    assert shape(a) == {"codesys", "codesys.timeout_s", "modes"}
    assert shape(b) == {"codesys", "codesys.timeout_s", "modes", "libraries"}
    assert "runtime.gateway.port" in shape(template_config())
