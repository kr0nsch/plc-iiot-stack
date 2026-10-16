"""Общие фикстуры тестов эмулятора."""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from typing import Any

import pytest

TESTS_DIR = Path(__file__).resolve().parent
EMULATOR_DIR = TESTS_DIR.parent
REPO_DIR = EMULATOR_DIR.parent
SCHEMA_DIR = REPO_DIR / "schema"

if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))  # mini_broker


def load_schema(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="session")
def validators() -> dict[str, Any]:
    """Валидаторы JSON Schema (draft 2020-12) для всех видов сообщений стенда."""
    jsonschema = pytest.importorskip("jsonschema")
    if not SCHEMA_DIR.is_dir():
        pytest.skip("нет каталога schema/ (тесты запущены вне репозитория)")
    out: dict[str, Any] = {}
    for kind in ("telemetry", "alarm", "command", "command_ack", "status"):
        schema = load_schema(f"{kind}.schema.json")
        cls = jsonschema.validators.validator_for(schema)
        cls.check_schema(schema)
        out[kind] = cls(schema, format_checker=cls.FORMAT_CHECKER)
    return out


@pytest.fixture(scope="session")
def topic_patterns() -> dict[str, Any]:
    import re

    topics = load_schema("topics.json")
    return {name: re.compile(c["pattern"]) for name, c in topics["classes"].items()}


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port
