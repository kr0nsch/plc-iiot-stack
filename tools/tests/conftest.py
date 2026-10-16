"""Общие фикстуры тестов инструментов (tools/)."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES = TESTS_DIR / "fixtures"
SAMPLE = FIXTURES / "sample"
GOLDEN = TESTS_DIR / "golden"
REPO_ROOT = TESTS_DIR.parent.parent

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
