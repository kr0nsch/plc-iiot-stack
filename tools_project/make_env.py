"""Создание и пополнение ``.env`` стенда из ``.env.example``.

Назначение: ``make env`` / ``make.ps1 env``. Значения ``change-me`` заменяются случайными паролями
(``secrets``), остальные копируются как есть. Существующий ``.env`` не перезаписывается: в него
только дописываются ключи, которых нет (например, после обновления ``.env.example``). В Linux и macOS
права файла — 0600 (только владелец): с умолчанием umask 022 пароли читал бы любой пользователь узла.
Автор: <ИМЯ ФАМИЛИЯ>. Версия: 1.1. Описание — docs/ARCHITECTURE.md, раздел «Секреты и настройки».
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path

PLACEHOLDER = "change-me"
KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$")
# Токен администратора InfluxDB длиннее паролей
LONG_SECRET_KEYS = frozenset({"INFLUX_ADMIN_TOKEN", "NODERED_CREDENTIAL_SECRET", "GRAFANA_SECRET_KEY"})


def random_secret(key: str) -> str:
    """Пароль из [A-Za-z0-9_-], первый символ — буква или цифра (не примут за ключ командной строки)."""
    nbytes = 48 if key in LONG_SECRET_KEYS else 24
    while True:
        value = secrets.token_urlsafe(nbytes)
        if value[0].isalnum():
            return value


def parse_keys(text: str) -> dict[str, str]:
    """Ключи и значения файла KEY=VALUE (комментарии и пустые строки пропускаются)."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = KEY_RE.match(line)
        if match:
            out[match.group(1)] = match.group(2).strip()
    return out


def render_line(line: str) -> str:
    """Строка .env.example → строка .env: change-me заменяется случайным значением."""
    match = KEY_RE.match(line)
    if match and not line.lstrip().startswith("#") and match.group(2).strip() == PLACEHOLDER:
        return f"{match.group(1)}={random_secret(match.group(1))}"
    return line


def restrict_permissions(target: Path) -> None:
    """Права 0600 на файл секретов (POSIX); в Windows права наследуются от каталога профиля."""
    if os.name == "posix":
        os.chmod(target, 0o600)


def make_env(example: Path, target: Path) -> list[str]:
    """Создать или пополнить target; возвращает список добавленных ключей."""
    example_text = example.read_text(encoding="utf-8")
    if not target.exists():
        lines = [render_line(line) for line in example_text.splitlines()]
        # Файл сразу создаётся с правами 0600: секреты ни на миг не доступны другим пользователям
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        restrict_permissions(target)
        return list(parse_keys(example_text))
    restrict_permissions(target)
    existing = parse_keys(target.read_text(encoding="utf-8"))
    missing = [
        line
        for line in example_text.splitlines()
        if (m := KEY_RE.match(line)) and not line.lstrip().startswith("#") and m.group(1) not in existing
    ]
    if missing:
        with target.open("a", encoding="utf-8", newline="\n") as f:
            f.write("\n# Добавлено make env из .env.example\n")
            for line in missing:
                f.write(render_line(line) + "\n")
    return [m.group(1) for line in missing if (m := KEY_RE.match(line))]


def main(argv: Sequence[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="Создать или пополнить .env из .env.example")
    ap.add_argument("--example", type=Path, default=root / ".env.example")
    ap.add_argument("--env", type=Path, default=root / ".env")
    args = ap.parse_args(argv)
    existed = args.env.exists()
    added = make_env(args.example, args.env)
    if not existed:
        print(f"создан {args.env.name}: значения {PLACEHOLDER} заменены случайными паролями")
    elif added:
        print(f"в {args.env.name} добавлены ключи: {', '.join(added)}")
    else:
        print(f"{args.env.name} актуален")
    leftovers = [k for k, v in parse_keys(args.env.read_text(encoding="utf-8")).items() if v == PLACEHOLDER]
    if leftovers:
        print(f"внимание: в {args.env.name} остались значения {PLACEHOLDER}: {', '.join(leftovers)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
