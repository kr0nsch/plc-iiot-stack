"""Тесты tools/check/st_lint.py: каждое правило — срабатывание и отсутствие срабатывания."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import st_lint
from conftest import SAMPLE, MakeTree

BOM = chr(0xFEFF)
HEADER = (
    "(*\n"
    "    Назначение: проверка линтера\n"
    "    Автор: <ИМЯ ФАМИЛИЯ>\n"
    "    Версия: 1.0.0\n"
    "    Документ: docs/ARCHITECTURE.md\n"
    "*)\n"
)


def pou(
    name: str,
    variables: str = "",
    impl: str = ";\n",
    kind: str = "FUNCTION_BLOCK",
    header: str = HEADER,
    subdir: str = "src",
) -> dict[str, str]:
    ret = " : BOOL" if kind == "FUNCTION" else ""
    decl = f"{header}{kind} {name}{ret}\nVAR\n{variables}END_VAR\n"
    base = f"{subdir}/POUs/{name}/{name}"
    return {f"{base}.decl.st": decl, f"{base}.impl.st": impl}


def config(**overrides: Any) -> dict[str, Any]:
    cfg = st_lint.load_config(st_lint.DEFAULT_CONFIG_PATH)
    return st_lint._merge(cfg, overrides)


def run(root: Path, cfg: dict[str, Any] | None = None) -> list[st_lint.Finding]:
    findings, _ = st_lint.lint(str(root), cfg or config(), ["src", "tests"])
    return findings


def hits(root: Path, rule: str, cfg: dict[str, Any] | None = None) -> list[tuple[str, int, int]]:
    return [(f.path, f.line, f.col) for f in run(root, cfg) if f.rule == rule]


def test_sample_is_clean() -> None:
    findings, files = st_lint.lint(str(SAMPLE), config())
    assert findings == []
    assert files == 46


def test_toml_matches_defaults() -> None:
    """tools/check/st_lint.toml повторяет значения по умолчанию из st_lint.py."""
    assert st_lint.load_config(st_lint.DEFAULT_CONFIG_PATH) == st_lint.DEFAULT_CONFIG


def test_clean_pou_has_no_findings(make_tree: MakeTree) -> None:
    root = make_tree(pou("FB_A", "    iCount : INT;\n", "iCount := iCount + 1;\n"))
    assert run(root) == []


# --- STL001 -------------------------------------------------------------------


def test_stl001_missing_header(make_tree: MakeTree) -> None:
    root = make_tree(pou("FB_A", header=""))
    assert hits(root, "STL001") == [("src/POUs/FB_A/FB_A.decl.st", 1, 1)]


def test_stl001_missing_keyword(make_tree: MakeTree) -> None:
    root = make_tree(pou("FB_A", header="// Назначение: x\n// Автор: y\n// Документ: docs/A.md\n"))
    findings = [f for f in run(root) if f.rule == "STL001"]
    assert len(findings) == 1 and "версия" in findings[0].message and findings[0].line == 4


def test_stl001_requires_docs_link(make_tree: MakeTree) -> None:
    root = make_tree(pou("FB_A", header="// Назначение: x\n// Автор: y\n// Версия: 1\n// Документ: ТЗ\n"))
    assert [f.message for f in run(root) if f.rule == "STL001"] == ["в заголовке POU нет ссылки на документ в docs/"]


def test_stl001_header_after_keyword_line_is_ok(make_tree: MakeTree) -> None:
    files = pou("FB_A", header="")
    files["src/POUs/FB_A/FB_A.decl.st"] = "FUNCTION_BLOCK FB_A\n" + HEADER + "VAR\nEND_VAR\n"
    assert hits(make_tree(files), "STL001") == []


def test_stl001_not_for_duts(make_tree: MakeTree) -> None:
    root = make_tree({"src/DUTs/E_A.dut.st": "TYPE E_A :\n(\n    A\n);\nEND_TYPE\n"})
    assert hits(root, "STL001") == []


# --- STL002, STL003 -------------------------------------------------------------


def test_stl002_tabs(make_tree: MakeTree) -> None:
    root = make_tree(pou("FB_A", "\tiX : INT;\n"))
    assert hits(root, "STL002") == [("src/POUs/FB_A/FB_A.decl.st", 9, 1)]
    assert hits(make_tree(pou("FB_A", "    iX : INT;\n")), "STL002") == []


def test_stl003_line_length(make_tree: MakeTree) -> None:
    long_comment = "// " + "x" * 117  # 120 символов — допустимо
    root = make_tree(pou("FB_A", impl=f"{long_comment}\n{long_comment}x\n"))
    assert hits(root, "STL003") == [("src/POUs/FB_A/FB_A.impl.st", 2, 121)]
    cfg = config(lint={"max_line_length": 80})
    assert len(hits(root, "STL003", cfg)) == 2


# --- STL004 -----------------------------------------------------------------------


def test_stl004_todo_without_issue(make_tree: MakeTree) -> None:
    impl = (
        "// TODO(#12) есть номер\n// TODO нет номера\n(* первая строка\n"
        "   FIXME тоже *)\ns := 'TODO в строке';\nTODO_X := 1;\n"
    )
    root = make_tree(pou("FB_A", impl=impl))
    assert hits(root, "STL004") == [("src/POUs/FB_A/FB_A.impl.st", 2, 4), ("src/POUs/FB_A/FB_A.impl.st", 4, 4)]


# --- STL005, STL010 ---------------------------------------------------------------


def test_stl005_non_ascii_identifier(make_tree: MakeTree) -> None:
    impl = 'xПуск := TRUE; // комментарий по-русски\nws := "строка";\nx := 1 « 2;\n'
    root = make_tree(pou("FB_A", impl=impl))
    assert hits(root, "STL005") == [("src/POUs/FB_A/FB_A.impl.st", 1, 1), ("src/POUs/FB_A/FB_A.impl.st", 3, 8)]


def test_stl010_cyrillic_in_string(make_tree: MakeTree) -> None:
    impl = "s := 'Пуск';\nws := \"Пуск\";\ns := 'Start';\n"
    root = make_tree(pou("FB_A", impl=impl))
    assert hits(root, "STL010") == [("src/POUs/FB_A/FB_A.impl.st", 1, 6)]


# --- STL006 -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("files", "path"),
    [
        (pou("Motor"), "src/POUs/Motor/Motor.decl.st"),
        (pou("Main", kind="PROGRAM"), "src/POUs/Main/Main.decl.st"),
        (pou("Clamp", kind="FUNCTION"), "src/POUs/Clamp/Clamp.decl.st"),
        (pou("FB_", kind="FUNCTION_BLOCK"), "src/POUs/FB_/FB_.decl.st"),
        (pou("FB_Prg", kind="PROGRAM"), "src/POUs/FB_Prg/FB_Prg.decl.st"),
        ({"src/DUTs/MotorCmd.dut.st": "TYPE MotorCmd :\nSTRUCT\n    xA : BOOL;\nEND_STRUCT\nEND_TYPE\n"}, None),
        ({"src/DUTs/Mode.dut.st": "TYPE Mode :\n(\n    A\n);\nEND_TYPE\n"}, None),
        ({"src/DUTs/Raw.dut.st": "TYPE Raw :\nUNION\n    dwA : DWORD;\nEND_UNION\nEND_TYPE\n"}, None),
        ({"src/GVLs/Io.gvl.st": "VAR_GLOBAL\n    xA : BOOL;\nEND_VAR\n"}, None),
        ({"src/Interfaces/Resettable/Resettable.itf.st": "INTERFACE Resettable\n"}, None),
    ],
)
def test_stl006_object_prefixes(make_tree: MakeTree, files: dict[str, str], path: str | None) -> None:
    found = hits(make_tree(files), "STL006")
    expected = path or next(iter(files))
    assert [p for p, _, _ in found] == [expected]


def test_stl006_alias_is_not_checked(make_tree: MakeTree) -> None:
    assert hits(make_tree({"src/DUTs/Percent.dut.st": "TYPE Percent : REAL; END_TYPE\n"}), "STL006") == []


def test_stl006_members(make_tree: MakeTree) -> None:
    files = pou("FB_A")
    files.update(
        {
            "src/POUs/FB_A/reset.method.decl.st": "METHOD reset\n",
            "src/POUs/FB_A/reset.method.impl.st": ";\n",
            "src/POUs/FB_A/FB_init.method.decl.st": "METHOD FB_init : BOOL\n",
            "src/POUs/FB_A/FB_init.method.impl.st": ";\n",
            "src/POUs/FB_A/Do_It.method.decl.st": "METHOD Do_It\n",
            "src/POUs/FB_A/Do_It.method.impl.st": ";\n",
            "src/POUs/FB_A/Value.prop.decl.st": "PROPERTY Value : INT\n",
            "src/POUs/FB_A/Value.get.impl.st": "Value := 1;\n",
        }
    )
    assert sorted(p for p, _, _ in hits(make_tree(files), "STL006")) == [
        "src/POUs/FB_A/Do_It.method.decl.st",
        "src/POUs/FB_A/reset.method.decl.st",
    ]


# --- STL007 -----------------------------------------------------------------------


def stl007_names(root: Path, cfg: dict[str, Any] | None = None) -> list[str]:
    return [f.message.split()[1] for f in run(root, cfg) if f.rule == "STL007"]


def test_stl007_variable_prefixes(make_tree: MakeTree) -> None:
    variables = (
        "    iCount : INT;\n    xCount : INT;\n    diTotal : DINT;\n    iTotal : DINT;\n    stCmd : ST_Cmd;\n"
        "    cmd : ST_Cmd;\n    aVals : ARRAY[1..3] OF INT;\n    pX : POINTER TO INT;\n    refX : REFERENCE TO INT;\n"
        "    fbT : TON;\n    tmr : TON;\n    fbM : Lib.FB_Motor;\n    itfX : I_X;\n    eMode : E_Mode;\n"
        "    wsName : WSTRING(80);\n    sName : STRING[80];\n    x : BOOL;\n    xa : BOOL;\n    custom : T_Custom;\n"
        "    xIn AT %IX0.0 : BOOL;\n    tDelay, wrong : TIME;\n"
    )
    root = make_tree(pou("FB_A", variables))
    assert stl007_names(root) == ["xCount", "iTotal", "cmd", "tmr", "x", "xa", "wrong"]


def test_stl007_constants_upper_snake(make_tree: MakeTree) -> None:
    files = {
        "src/GVLs/GVL_Const.gvl.st": "VAR_GLOBAL CONSTANT\n    MAX_SPEED : REAL := 1.0;\n"
        "    maxSpeed : REAL := 2.0;\nEND_VAR\n"
    }
    files.update(pou("FB_A", impl=";\n"))
    files["src/POUs/FB_A/FB_A.decl.st"] += "VAR CONSTANT\n    C_LIMIT : INT := 3;\n    Limit : INT := 4;\nEND_VAR\n"
    assert sorted(stl007_names(make_tree(files))) == ["Limit", "maxSpeed"]


def test_stl007_struct_members_and_gvl(make_tree: MakeTree) -> None:
    files = {
        "src/DUTs/ST_A.dut.st": "TYPE ST_A :\nSTRUCT\n    xOk : BOOL;\n    bad : BOOL;\nEND_STRUCT\nEND_TYPE\n",
        "src/GVLs/GVL_Io.gvl.st": "VAR_GLOBAL\n    rLevel_m : REAL;\n    level : REAL;\nEND_VAR\n",
    }
    assert sorted(stl007_names(make_tree(files))) == ["bad", "level"]


def test_stl007_allow_names(make_tree: MakeTree) -> None:
    root = make_tree(pou("FB_A", "    i : INT;\n"))
    assert stl007_names(root) == ["i"]
    assert stl007_names(root, config(rules={"STL007": {"allow_names": ["i"]}})) == []


# --- STL008 -----------------------------------------------------------------------


def test_stl008_magic_numbers(make_tree: MakeTree) -> None:
    impl = (
        "iX := iY * 7;\n"
        "iX := 0; iX := 1; iX := 2; rX := 1.0; rX := -1.0;\n"
        "aBuf[3] := 1;\n"
        "xBit := wStatus.3;\n"
        "wMask := wStatus AND 16#FF;\n"
        "tWait := T#5S;\n"
        "CASE iStep OF\n    5:\n        iX := 1;\n    10, 20..30:\n        iX := 2;\nEND_CASE\n"
        "rY := rX * 0.5;\n"
    )
    root = make_tree(pou("FB_A", impl=impl))
    assert hits(root, "STL008") == [("src/POUs/FB_A/FB_A.impl.st", 1, 12), ("src/POUs/FB_A/FB_A.impl.st", 13, 12)]


def test_stl008_tests_excluded_and_method_bodies_checked(make_tree: MakeTree) -> None:
    files = pou("FB_A_Test", impl="rX := 42.0;\n", subdir="tests")
    files.update(pou("FB_B"))
    files["src/POUs/FB_B/Calc.method.decl.st"] = "METHOD Calc : INT\n"
    files["src/POUs/FB_B/Calc.method.impl.st"] = "Calc := 42;\n"
    assert hits(make_tree(files), "STL008") == [("src/POUs/FB_B/Calc.method.impl.st", 1, 9)]


def test_stl008_declarations_not_checked(make_tree: MakeTree) -> None:
    root = make_tree(pou("FB_A", "    aBuf : ARRAY[1..10] OF INT;\n    iMax : INT := 100;\n"))
    assert hits(root, "STL008") == []


def test_suppression_same_and_previous_line(make_tree: MakeTree) -> None:
    impl = (
        "iX := iY * 7; // lint:allow STL008 коэффициент из паспорта насоса\n"
        "// lint:allow STL008 число полюсов двигателя\n"
        "iZ := iY * 4;\n"
        "iW := iY * 9;\n"
        "(* lint:allow STL008, STL004 причина *)\n"
        "iV := iY * 3; // TODO без номера\n"
    )
    root = make_tree(pou("FB_A", impl=impl))
    assert hits(root, "STL008") == [("src/POUs/FB_A/FB_A.impl.st", 4, 12)]
    assert hits(root, "STL004") == []


def test_stl012_bad_suppressions(make_tree: MakeTree) -> None:
    impl = "iX := iY * 7; // lint:allow STL008\niZ := 1; // lint:allow STL999 причина\niQ := 1; // lint:allow\n"
    root = make_tree(pou("FB_A", impl=impl))
    assert hits(root, "STL012") == [
        ("src/POUs/FB_A/FB_A.impl.st", 1, 18),
        ("src/POUs/FB_A/FB_A.impl.st", 2, 13),
        ("src/POUs/FB_A/FB_A.impl.st", 3, 13),
    ]
    assert hits(root, "STL008") == [("src/POUs/FB_A/FB_A.impl.st", 1, 12)]


# --- STL009 -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "line", "fragment"),
    [
        (BOM + "x := 1;\n", 1, "BOM"),
        ("x := 1;\r\ny := 2;\r\n", 1, "CRLF"),
        ("x := 1;\ny := 2;", 2, "нет перевода строки"),
        ("x := 1;\n\n\n", 2, "пустые строки"),
        ("x := 1;  \ny := 2;\n", 1, "хвостовые пробелы"),
    ],
)
def test_stl009_not_normalized(make_tree: MakeTree, raw: str, line: int, fragment: str) -> None:
    root = make_tree(pou("FB_A", impl=raw))
    found = [f for f in run(root) if f.rule == "STL009"]
    assert [(f.line, fragment in f.message) for f in found] == [(line, True)]


def test_stl009_encoding(tmp_path: Path) -> None:
    from conftest import write_tree

    root = write_tree(tmp_path, pou("FB_A"))
    (root / "src/POUs/FB_A/FB_A.impl.st").write_bytes("// Пуск\n".encode("cp1251"))
    rules = {f.rule for f in run(root)}
    assert "STL009" in rules and "LAY007" in rules


def test_stl009_empty_file_is_fine(make_tree: MakeTree) -> None:
    files = {
        "src/Interfaces/I_A/I_A.itf.st": "INTERFACE I_A\n",
        "src/Interfaces/I_A/V.prop.decl.st": "PROPERTY V : INT\n",
    }
    files["src/Interfaces/I_A/V.get.decl.st"] = ""
    assert hits(make_tree(files), "STL009") == []


# --- STL011 -----------------------------------------------------------------------


def test_stl011_cycle_counting(make_tree: MakeTree) -> None:
    impl = (
        "iCycleCount := iCycleCount + 1;\n"
        "iCount := iCount + 1;\n"
        "IF iCount >= GVL_Const.T_DELAY_CYCLES THEN\n    xDone := TRUE;\nEND_IF\n"
        "udiStarts := udiStarts + 1;\n"
        "stSts.iTicks := 1 + stSts.iTicks;\n"
    )
    root = make_tree(pou("FB_A", impl=impl))
    found = [f for f in run(root) if f.rule == "STL011"]
    assert [(f.line, f.severity) for f in found] == [(1, "warning"), (2, "warning"), (7, "warning")]


# --- Замечания раскладки и настройки ----------------------------------------------


def test_layout_issues_reported(make_tree: MakeTree) -> None:
    files = pou("FB_A")
    files["src/POUs/FB_A/FB_A.decl.st"] = HEADER + "FUNCTION_BLOCK FB_B\nVAR\nEND_VAR\n"
    assert hits(make_tree(files), "LAY002") == [("src/POUs/FB_A/FB_A.decl.st", 7, 1)]


def test_severity_off_and_exclude(make_tree: MakeTree) -> None:
    root = make_tree(pou("FB_A", "\tiX : INT;\n", impl="iX := 7;\n"))
    assert hits(root, "STL002", config(severity={"STL002": "off"})) == []
    assert hits(root, "STL008", config(rules={"STL008": {"exclude": ["src/POUs/FB_A/*"]}})) == []
    assert run(root, config(lint={"exclude": ["src/*"]})) == []


@pytest.mark.parametrize(
    "text",
    [
        '[severity]\nSTL999 = "error"\n',
        '[severity]\nSTL001 = "fatal"\n',
        "[rules.STL999]\nx = 1\n",
        "[lint\n",
    ],
)
def test_bad_config(tmp_path: Path, text: str) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(st_lint.ConfigError):
        st_lint.load_config(str(path))
    assert st_lint.main(["--root", str(tmp_path), "--config", str(path)]) == 2


def test_missing_config_file(tmp_path: Path) -> None:
    with pytest.raises(st_lint.ConfigError):
        st_lint.load_config(str(tmp_path / "none.toml"))


# --- Командная строка ------------------------------------------------------------


def test_cli_text_and_exit_codes(make_tree: MakeTree, capsys: pytest.CaptureFixture[str]) -> None:
    assert st_lint.main(["--root", str(SAMPLE)]) == 0
    assert "ошибок 0" in capsys.readouterr().out
    root = make_tree(pou("FB_A", impl="iX := 7;\n"))
    assert st_lint.main(["--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "src/POUs/FB_A/FB_A.impl.st:1:7: STL008 [ошибка]" in out


def test_cli_strict_and_warnings(make_tree: MakeTree, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_tree(pou("FB_A", "    iCycleCount : INT;\n", impl="iCycleCount := iCycleCount + 1;\n"))
    assert st_lint.main(["--root", str(root)]) == 0
    assert st_lint.main(["--root", str(root), "--strict"]) == 1
    capsys.readouterr()


def test_cli_json(make_tree: MakeTree, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_tree(pou("FB_A", impl="iX := 7;\n"))
    assert st_lint.main(["--root", str(root), "--json", "--no-config"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["summary"] == {"files": 2, "errors": 1, "warnings": 0}
    assert data["findings"][0]["rule"] == "STL008"


def test_cli_list_rules(capsys: pytest.CaptureFixture[str]) -> None:
    assert st_lint.main(["--list-rules"]) == 0
    out = capsys.readouterr().out
    assert all(rule in out for rule in st_lint.RULES)


def test_cli_explicit_paths(make_tree: MakeTree) -> None:
    files = pou("FB_A", impl="iX := 7;\n", subdir="tests")
    root = make_tree(files)
    assert st_lint.main(["--root", str(root), "src"]) == 0


@pytest.mark.parametrize(
    ("type_text", "prefix"),
    [
        ("BOOL", "x"),
        ("STRING(80)", "s"),
        ("ARRAY[1..3] OF INT", "a"),
        ("POINTER TO ST_X", "p"),
        ("REF_TO INT", "ref"),
        ("CfUnit.FB_TestSuite", "fb"),
        ("R_TRIG", "fb"),
        ("T_Custom", None),
        ("INT(0..100)", "i"),
    ],
)
def test_prefix_for_type(type_text: str, prefix: str | None) -> None:
    assert st_lint.prefix_for_type(type_text, st_lint.DEFAULT_CONFIG["rules"]["STL007"]) == prefix
