"""Встраивание ПЛК-части IIoT-стека в рабочую копию флагмана КНС-1 (kns-pump-station).

Назначение: шаги 2–4, 6 и 7 раздела 11 docs/MANUAL_STEPS.md одной командой — в рабочую копию флагмана,
которую потом собирают его ``cds.py build`` и ``cds.py test``:

- ядро ``src/`` этого репозитория (без ``src/POUs/PRG_Main`` и ``src/GVLs/GVL_Const.gvl.st``) и привязка
  ``flagship/src/`` — в ``src/`` флагмана; каталоги ``POUs/Iiot`` сливаются;
- константы ``GVL_Const`` этого репозитория — раздел «IIoT» в ``GVL_Const`` флагмана между строками-метками
  (повторный запуск заменяет раздел); совпадение имён с константами флагмана — ошибка;
- ``tools/codesys/config.json`` флагмана: ``PRG_Iiot`` — в задаче ``MainTask`` после ``PRG_Devices`` и в
  ``library.exclude`` (программа задачи в библиотеку флагмана не входит);
- ``tools_project/codesys/symbol_rules.json`` флагмана: правило ``GVL_Iiot`` (``stIiotCfg``, ``stIiotSts`` —
  чтение). Без него ``symbol_config.py`` флагмана снимает доступ с переменных без правила, и ``GVL_Iiot`` в
  символы OPC UA не попадает: атрибут ``symbol`` в исходнике этого не меняет (проверено 19.10.2026);
- с тестами (по умолчанию): наборы ``tests/`` и ``flagship/tests/`` — в ``tests/POUs/Iiot``, типы подменного
  клиента — в ``tests/DUTs/Iiot``, экземпляры наборов — ``tests/GVLs/GVL_TestsIiot.gvl.st`` (у флагмана
  наборы объявляются в списках команд с атрибутом ``linkalways``, а не в ``PRG_Tests``).

Правки текстовые: остальная разметка файлов флагмана не меняется; JSON после правки разбирается и
сверяется. Повторный запуск ничего не меняет. Свою рабочую копию флагмана (не общую, в которой идёт
работа) — например, ``git clone ../kns-pump-station <каталог>``.

Автор: kr0nsch. Документ: docs/MANUAL_STEPS.md, раздел 11.

Запуск из корня репозитория::

    python tools_project/flagship_embed.py --repo <рабочая копия флагмана>
    python tools_project/flagship_embed.py --repo <...> --no-tests

Код выхода: 0 — готово, 1 — флагман не подходит (нет файлов, конфликт имён констант), 2 — аргументы.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DEFAULT_FLAGSHIP = REPO.parent / "kns-pump-station"
TOOL = "tools_project/flagship_embed.py"

PRG = "PRG_Iiot"
AFTER = "PRG_Devices"
MAIN_TASK = "MainTask"
CONST_FILE = Path("src/GVLs/GVL_Const.gvl.st")
CONFIG_FILE = Path("tools/codesys/config.json")
RULES_FILE = Path("tools_project/codesys/symbol_rules.json")
TESTS_GVL = Path("tests/GVLs/GVL_TestsIiot.gvl.st")
SKIP_SRC = {Path("POUs/PRG_Main"), Path("GVLs/GVL_Const.gvl.st")}
SYMBOL_RULE: dict[str, Any] = {"gvl": "GVL_Iiot", "vars": ["stIiotCfg", "stIiotSts"], "access": "Read"}

CONST_BEGIN = "    // ===== IIoT (проект 06 plc-iiot-stack; вставляет tools_project/flagship_embed.py) ====="
CONST_END = "    // ===== конец раздела IIoT ====="
_CONST_NAME = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", re.MULTILINE)
_SUITE = re.compile(r"^\s*(fb[A-Za-z0-9_]*)\s*:\s*(FB_[A-Za-z0-9_]*_Test)\s*;", re.MULTILINE)


class EmbedError(Exception):
    """Рабочая копия флагмана не подходит для встраивания."""


@dataclass
class Report:
    """Что изменилось в рабочей копии флагмана."""

    written: list[str] = field(default_factory=list)
    unchanged: int = 0

    def put(self, root: Path, rel: Path, text: str) -> None:
        path = root / rel
        if path.exists() and path.read_text(encoding="utf-8") == text:
            self.unchanged += 1
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        self.written.append(rel.as_posix())


# --- исходники ST ------------------------------------------------------------------------------------
def st_files(base: Path, skip: set[Path] | None = None) -> list[Path]:
    """Файлы ``*.st`` под ``base`` (пути относительно него), кроме ``skip`` и всего под ними."""
    skip = skip or set()
    out = []
    for path in sorted(base.rglob("*.st")):
        rel = path.relative_to(base)
        if any(rel == s or s in rel.parents for s in skip):
            continue
        out.append(rel)
    return out


def copy_sources(src: Path, dst: Path, rel_dst: Path, report: Report, skip: set[Path] | None = None) -> None:
    for rel in st_files(src, skip):
        report.put(dst, rel_dst / rel, (src / rel).read_text(encoding="utf-8"))


# --- GVL_Const ---------------------------------------------------------------------------------------
def constants_body(text: str) -> list[str]:
    """Строки между ``VAR_GLOBAL CONSTANT`` и ``END_VAR`` (без них)."""
    lines = text.splitlines()
    try:
        start = next(i for i, s in enumerate(lines) if s.strip().startswith("VAR_GLOBAL CONSTANT"))
        end = max(i for i, s in enumerate(lines) if s.strip() == "END_VAR")
    except (StopIteration, ValueError) as exc:
        raise EmbedError("GVL_Const: нет VAR_GLOBAL CONSTANT … END_VAR") from exc
    return lines[start + 1 : end]


def const_names(lines: Sequence[str]) -> set[str]:
    names = set()
    for line in lines:
        code = line.split("//", 1)[0]
        m = _CONST_NAME.match(code)
        if m:
            names.add(m.group(1))
    return names


def merge_constants(flagship_text: str, iiot_text: str) -> str:
    """``GVL_Const`` флагмана с разделом IIoT перед последним ``END_VAR`` (старый раздел заменяется)."""
    lines = flagship_text.splitlines()
    if CONST_BEGIN in lines:
        begin = lines.index(CONST_BEGIN)
        try:
            end = lines.index(CONST_END, begin)
        except ValueError as exc:
            raise EmbedError("GVL_Const флагмана: начало раздела IIoT без конца") from exc
        del lines[begin : end + 1]
        if begin > 0 and lines[begin - 1] == "":
            del lines[begin - 1]
    body = constants_body(iiot_text)
    clash = sorted(const_names(constants_body("\n".join(lines))) & const_names(body))
    if clash:
        raise EmbedError(f"GVL_Const: имена уже есть у флагмана: {', '.join(clash)}")
    try:
        end_var = max(i for i, s in enumerate(lines) if s.strip() == "END_VAR")
    except ValueError as exc:
        raise EmbedError("GVL_Const флагмана: нет END_VAR") from exc
    lines[end_var:end_var] = ["", CONST_BEGIN, *body, CONST_END]
    return "\n".join(lines) + "\n"


# --- config.json и symbol_rules.json ------------------------------------------------------------------
def _json(text: str, what: str) -> Any:
    try:
        return json.loads(text)
    except ValueError as exc:
        raise EmbedError(f"{what}: не JSON после правки ({exc})") from exc


def _main_pous(cfg: Any) -> list[str]:
    for task in cfg["modes"]["normal"]["tasks"]:
        if task["name"] == MAIN_TASK:
            return list(task["pous"])
    raise EmbedError(f"{CONFIG_FILE}: нет задачи {MAIN_TASK} в modes.normal")


def patch_config(text: str) -> str:
    """``PRG_Iiot`` после ``PRG_Devices``: в ``MainTask`` и в ``library.exclude`` (текстовая правка)."""
    cfg = _json(text, str(CONFIG_FILE))
    pous = _main_pous(cfg)
    exclude = list(cfg["library"]["exclude"])
    if AFTER not in pous or AFTER not in exclude:
        raise EmbedError(f"{CONFIG_FILE}: нет {AFTER} в {MAIN_TASK} или library.exclude")
    if PRG in pous and PRG in exclude:
        return text
    old, new = f'"{AFTER}"', f'"{AFTER}", "{PRG}"'
    if text.count(old) != 2 or PRG in text:
        raise EmbedError(f"{CONFIG_FILE}: ожидалось ровно два вхождения {old} (задача и library.exclude)")
    out = text.replace(old, new)
    cfg = _json(out, str(CONFIG_FILE))
    pous = _main_pous(cfg)
    if pous.index(PRG) != pous.index(AFTER) + 1 or PRG not in cfg["library"]["exclude"]:
        raise EmbedError(f"{CONFIG_FILE}: правка не дала {PRG} после {AFTER}")
    return out


def patch_rules(text: str) -> str:
    """Правило ``GVL_Iiot`` последним в ``rules`` (если правила для ``GVL_Iiot`` ещё нет)."""
    data = _json(text, str(RULES_FILE))
    if any(rule.get("gvl") == SYMBOL_RULE["gvl"] for rule in data["rules"]):
        return text
    start = text.index('"rules"')
    close = text.index("\n  ]", start)
    line = json.dumps(SYMBOL_RULE, ensure_ascii=False)
    out = f"{text[:close]},\n    {line}{text[close:]}"
    if _json(out, str(RULES_FILE))["rules"][-1] != SYMBOL_RULE:
        raise EmbedError(f"{RULES_FILE}: правка не дала правило {SYMBOL_RULE['gvl']}")
    return out


# --- тесты -------------------------------------------------------------------------------------------
def suites(prg_tests_decl: str) -> list[tuple[str, str]]:
    """Экземпляры наборов из объявления ``PRG_Tests`` этого репозитория: (имя, тип)."""
    return _SUITE.findall(prg_tests_decl)


def tests_gvl(entries: Sequence[tuple[str, str]]) -> str:
    width = max(len(name) for name, _ in entries)
    rows = "\n".join(f"    {name.ljust(width)} : {kind};" for name, kind in entries)
    return (
        f"// AUTO-GENERATED by {TOOL} — не редактировать\n"
        "// Назначение: экземпляры наборов тестов ПЛК-части IIoT-стека (проект 06 plc-iiot-stack): JSON, ядро\n"
        "//             MQTT, таблицы GVL_IiotMap и привязка FB_IiotKnsMap к переменным флагмана. Объявление\n"
        "//             регистрирует набор в coUnit; {attribute 'linkalways'} — чтобы компилятор не выбросил\n"
        "//             список, на который никто не ссылается.\n"
        "// Автор:      kr0nsch\n"
        "// Версия:     0.2.0\n"
        "// Документ:   plc-iiot-stack, docs/MANUAL_STEPS.md, раздел 11\n"
        "{attribute 'qualified_only'}\n"
        "{attribute 'linkalways'}\n"
        "VAR_GLOBAL\n"
        f"{rows}\n"
        "END_VAR\n"
    )


def binding_suites(tests_dir: Path) -> list[tuple[str, str]]:
    """Наборы ``flagship/tests/POUs/Iiot/<FB_…_Test>``: экземпляр ``fb<имя без FB_ и _Test>Test``."""
    out = []
    for decl in sorted(tests_dir.glob("POUs/Iiot/FB_*_Test/FB_*_Test.decl.st")):
        kind = decl.parent.name
        out.append((f"fb{kind[3:-5]}Test", kind))
    return out


# --- встраивание -------------------------------------------------------------------------------------
def check_flagship(root: Path) -> None:
    missing = [p.as_posix() for p in (CONST_FILE, CONFIG_FILE, RULES_FILE) if not (root / p).is_file()]
    if missing:
        raise EmbedError(f"{root}: не рабочая копия kns-pump-station (нет {', '.join(missing)})")


def embed(root: Path, with_tests: bool = True, repo: Path = REPO) -> Report:
    check_flagship(root)
    report = Report()
    copy_sources(repo / "src", root, Path("src"), report, SKIP_SRC)
    copy_sources(repo / "flagship" / "src", root, Path("src"), report)
    report.put(
        root,
        CONST_FILE,
        merge_constants(
            (root / CONST_FILE).read_text(encoding="utf-8"), (repo / CONST_FILE).read_text(encoding="utf-8")
        ),
    )
    report.put(root, CONFIG_FILE, patch_config((root / CONFIG_FILE).read_text(encoding="utf-8")))
    report.put(root, RULES_FILE, patch_rules((root / RULES_FILE).read_text(encoding="utf-8")))
    if with_tests:
        tests = repo / "tests"
        copy_sources(tests / "POUs", root, Path("tests/POUs/Iiot"), report, {Path("PRG_Tests")})
        copy_sources(tests / "DUTs", root, Path("tests/DUTs/Iiot"), report)
        entries = suites((tests / "POUs/PRG_Tests/PRG_Tests.decl.st").read_text(encoding="utf-8"))
        flagship_tests = repo / "flagship" / "tests"
        if flagship_tests.is_dir():
            copy_sources(flagship_tests, root, Path("tests"), report)
            entries += binding_suites(flagship_tests)
        if not entries:
            raise EmbedError("tests/POUs/PRG_Tests: не найдены экземпляры наборов")
        report.put(root, TESTS_GVL, tests_gvl(entries))
    return report


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(os.environ.get("KNS_REPO", str(DEFAULT_FLAGSHIP))),
        help="рабочая копия флагмана (по умолчанию ../kns-pump-station или KNS_REPO)",
    )
    parser.add_argument("--no-tests", action="store_true", help="без наборов тестов")
    args = parser.parse_args(argv)
    try:
        report = embed(args.repo.resolve(), with_tests=not args.no_tests)
    except (EmbedError, OSError) as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1
    for rel in report.written:
        print(f"записан: {rel}")
    print(f"{args.repo}: записано {len(report.written)}, без изменений {report.unchanged}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
