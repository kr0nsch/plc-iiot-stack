"""Обоснования UnusedVariable в tools/check/iec_checker_allow.toml: перечисленные переменные действительно читаются.

iec_checker 0.4 не считает использованием обращения из методов ФБ (сборка варианта iec-checker выносит методы
в отдельные функции), вызов экземпляра ФБ и его методов, обращения к полям и переменные в границах FOR. Такие
ложные UnusedVariable обоснованы записями с перечнем имён в match. Тест не даёт обоснованию пережить
переменную: каждое имя объявлено в файлах записи, а в теле своего POU (или метода, или свойства) к нему есть
обращение вне комментариев и строк. Иначе переменная действительно не используется — её нужно убрать из кода
и из перечня. Сам iec_checker тесту не нужен; что каждая запись срабатывает, проверяет
test_integration_repository_sources шаблона (tools/tests/test_run_iec_checker.py, с --tests).
"""

from __future__ import annotations

import fnmatch
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOW = REPO_ROOT / "tools" / "check" / "iec_checker_allow.toml"
# match с перечнем имён: ': (A|B)$' или многострочно '(?x) :\s ( A | B )$'
_NAMES_MATCH = re.compile(r"^(?:\(\?x\)\s*:\\s|:\x20)\s*\(([A-Z0-9_|\s]+)\)\$$")
_COMMENT = re.compile(r"//[^\n]*|\(\*.*?\*\)|/\*.*?\*/", re.S)
_ST_STRING = re.compile(r"'(?:\$.|[^'$\n])*'|\"(?:\$.|[^\"$\n])*\"")


def _entries() -> list[dict[str, Any]]:
    data = tomllib.loads(ALLOW.read_text(encoding="utf-8"))
    return [e for e in data.get("allow", []) if e.get("id") == "UnusedVariable" and e.get("match")]


def _code(path: Path) -> str:
    """Текст ST без комментариев и строковых литералов."""
    return _ST_STRING.sub("''", _COMMENT.sub(" ", path.read_text(encoding="utf-8")))


def _bodies(decl: Path) -> list[Path]:
    """Где должно быть обращение к переменной из объявления decl."""
    if decl.name.endswith(".method.decl.st"):
        return [decl.with_name(decl.name.replace(".method.decl.st", ".method.impl.st"))]
    if decl.name.endswith(".prop.decl.st"):
        stem = decl.name.removesuffix(".prop.decl.st")
        return [decl.with_name(f"{stem}.get.impl.st"), decl.with_name(f"{stem}.set.impl.st")]
    # объявление POU: переменные видны в его теле, методах и аксессорах свойств
    return sorted(decl.parent.glob("*.impl.st"))


def _declares(decl: Path, name: str) -> bool:
    return re.search(rf"(?im)^\s*{name}\s*(?:AT\s+%\S+\s*)?:(?!=)", _code(decl)) is not None


def test_allow_has_unused_variable_lists() -> None:
    assert len(_entries()) >= 10


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: str(e["file"]))
def test_unused_variable_allow_lists_only_used_variables(entry: dict[str, Any]) -> None:
    m = _NAMES_MATCH.match(entry["match"])
    assert m, f"{entry['file']}: match — перечень имён ': (ИМЯ|ИМЯ)$' или '(?x) :\\s ( ИМЯ | ИМЯ )$'"
    names = [n.strip() for n in m.group(1).split("|")]
    assert all(re.fullmatch(r"[A-Z][A-Z0-9_]*", n) for n in names), names
    assert len(names) == len(set(names)), f"{entry['file']}: имена повторяются"
    files = [
        p
        for top in ("src", "tests")
        for p in sorted((REPO_ROOT / top).rglob("*.st"))
        if fnmatch.fnmatchcase(p.relative_to(REPO_ROOT).as_posix(), entry["file"])
    ]
    decls = [p for p in files if p.name.endswith(".decl.st")]
    assert decls, f"{entry['file']}: нет объявлений"
    for name in names:
        declaring = [d for d in decls if _declares(d, name)]
        assert declaring, f"{entry['file']}: {name} не объявлена — уберите имя из перечня"
        usage = re.compile(rf"\b{name}\b", re.IGNORECASE)
        for decl in declaring:
            bodies = [b for b in _bodies(decl) if b.is_file()]
            assert any(usage.search(_code(b)) for b in bodies), (
                f"{decl.relative_to(REPO_ROOT).as_posix()}: к {name} нет обращений — переменная не используется, "
                "обоснование неверно"
            )
