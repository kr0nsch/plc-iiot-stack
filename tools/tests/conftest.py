"""Общие фикстуры тестов инструментов (tools/)."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES = TESTS_DIR / "fixtures"
SAMPLE = FIXTURES / "sample"
GOLDEN = TESTS_DIR / "golden"
REPO_ROOT = TESTS_DIR.parent.parent
# Эталон настроек cds.py для тестов инструментов — копия tools/codesys/config.json шаблона. Тесты не читают
# config.json репозитория: в проектах он свой (библиотеки, задачи, библиотека репозитория). Живой config.json
# проверяет только test_cds_config.py — на уровне схемы (те же разделы и ключи, что у эталона).
CONFIG_TEMPLATE = FIXTURES / "config_template.json"
LIVE_CONFIG = REPO_ROOT / "tools" / "codesys" / "config.json"
# Эталон настроек st_lint (копия tools/check/st_lint.toml шаблона): tools/check/st_lint.toml принадлежит проекту,
# тесты линтера от него не зависят; живой файл проверяется только на разбор и известные ключи.
ST_LINT_TEMPLATE = FIXTURES / "st_lint_template.toml"
# Пример для понижения iec-checker: конструкции CODESYS, которых нет в грамматике iec_checker v0.4
LOWERING = FIXTURES / "lowering"
# Пример для карты строк после понижения: многострочные конструкции, метка «// @N» — номер строки в своём
# файле, строки с «= 1.5 THEN» (в любом регистре) дают PLCOPEN-CP8 (по ним интеграционный тест сверяет строки находок)
SOURCEMAP = FIXTURES / "sourcemap"
SOURCEMAP_MARK = "// @"
SOURCEMAP_CP8 = "= 1.5 THEN"


def sourcemap_lines(predicate: Callable[[str], bool]) -> set[tuple[str, int]]:
    """(путь от корня примера, номер строки) для строк примера sourcemap, где predicate(строка) истинно."""
    found: set[tuple[str, int]] = set()
    for path in sorted(SOURCEMAP.rglob("*.st")):
        rel = path.relative_to(SOURCEMAP).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if predicate(line):
                found.add((rel, number))
    return found


def template_config() -> dict[str, Any]:
    """Свежая копия эталона настроек (тесты могут её менять)."""
    data: dict[str, Any] = json.loads(CONFIG_TEMPLATE.read_text(encoding="utf-8"))
    return data


MakeTree = Callable[[dict[str, str]], Path]


def write_tree(root: Path, files: dict[str, str]) -> Path:
    """Создаёт файлы {путь posix: текст} под root (LF, UTF-8 без BOM)."""
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    return root


@pytest.fixture
def make_tree(tmp_path: Path) -> MakeTree:
    def make(files: dict[str, str]) -> Path:
        return write_tree(tmp_path / "repo", files)

    return make


@pytest.fixture
def sample_copy(tmp_path: Path) -> Path:
    """Копия фикстуры sample (src/ и tests/) во временном каталоге."""
    target = tmp_path / "sample"
    shutil.copytree(SAMPLE, target)
    return target


def find_plc() -> str | None:
    """Компилятор RuSTy для интеграционных тестов (как в run_rusty.find_compiler)."""
    import run_rusty

    try:
        return run_rusty.find_compiler()
    except run_rusty.ToolMissing:
        return None


def find_iec_checker() -> str | None:
    import run_iec_checker

    try:
        return run_iec_checker.find_binary()
    except run_iec_checker.ToolMissing:
        return None


def rusty_ready() -> bool:
    import run_rusty

    plc = find_plc()
    if plc is None:
        return False
    try:
        run_rusty.find_stdlib(plc)
    except run_rusty.ToolMissing:
        return False
    return True


requires_rusty = pytest.mark.skipif(not rusty_ready(), reason="нет компилятора RuSTy (plc) или его stdlib")
requires_iec_checker = pytest.mark.skipif(find_iec_checker() is None, reason="нет iec_checker")


def update_golden() -> bool:
    return os.environ.get("UPDATE_GOLDEN") == "1"
