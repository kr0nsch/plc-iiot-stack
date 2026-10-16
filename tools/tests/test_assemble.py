"""Тесты tools/assemble.py и tools/st_flavors.py: варианты iec, rusty, iec-checker."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import assemble
import st_flavors as F
import stlayout as L
from conftest import GOLDEN, SAMPLE, MakeTree, update_golden

GOLDEN_FLAVORS = {
    assemble.FLAVOR_IEC: [],
    assemble.FLAVOR_RUSTY: ["CfUnit"],
    assemble.FLAVOR_IEC_CHECKER: [],
}


def assemble_sample(flavor: str, namespaces: list[str] | None = None) -> assemble.AssembleResult:
    objects, issues = assemble.load_objects(str(SAMPLE), ["src", "tests"])
    assert issues == []
    return assemble.assemble_objects(objects, flavor, namespaces or [])


def read_dir(path: Path) -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(path.iterdir()) if p.is_file()}


# ---------------------------------------------------------------------------
# Эталоны (tools/tests/golden/<flavor>/); обновление: UPDATE_GOLDEN=1 pytest
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flavor", list(GOLDEN_FLAVORS))
def test_golden(tmp_path: Path, flavor: str) -> None:
    result = assemble_sample(flavor, GOLDEN_FLAVORS[flavor])
    out = tmp_path / flavor
    assemble.write_result(result, str(out))
    golden = GOLDEN / flavor
    if update_golden():
        golden.mkdir(parents=True, exist_ok=True)
        for old in golden.iterdir():
            old.unlink()
        for name, text in read_dir(out).items():
            (golden / name).write_bytes(text.encode("utf-8"))
    assert read_dir(out) == read_dir(golden)


def test_all_st_order() -> None:
    result = assemble_sample(assemble.FLAVOR_IEC)
    assert [u.name for u in result.units] == [
        "E_DeviceMode",
        "E_NamurStatus",
        "ST_DeviceSts",
        "ST_MotorCmd",
        "ST_MotorSts",
        "U_RawValue",
        "GVL_Const",
        "GVL_Io",
        "PVL_Retain",
        "I_Resettable",
        "I_Device",
        "F_Clamp",
        "FB_DeviceBase",
        "FB_F_Clamp_Test",
        "FB_Motor",
        "PRG_Main",
        "PRG_Tests",
    ]


def test_sourcemap_points_to_source_lines() -> None:
    """Каждая строка с источником в варианте iec совпадает со строкой исходного файла."""
    result = assemble_sample(assemble.FLAVOR_IEC)
    smap = assemble.SourceMap.from_result(result)
    for unit in [*result.units, result.all_unit]:
        name = assemble.ALL_FILE if unit is result.all_unit else unit.file_name
        lines = unit.text.split("\n")
        for number, text in enumerate(lines[:-1], 1):
            mapped = smap.lookup(name, number)
            if mapped is None:
                assert smap.is_synthetic(name, number)
                continue
            source, line = mapped
            source_lines = (SAMPLE / source).read_text(encoding="utf-8").split("\n")
            # строка заголовка свойства отличается только ключевым словом
            expected = text.replace("PROPERTY_GET", "PROPERTY").replace("PROPERTY_SET", "PROPERTY")
            assert source_lines[line - 1] == expected, (name, number)


@pytest.mark.parametrize("flavor", [assemble.FLAVOR_RUSTY, assemble.FLAVOR_IEC_CHECKER])
def test_flavors_keep_line_structure(flavor: str) -> None:
    """Замены не сдвигают строки: число строк фрагментов совпадает с картой."""
    result = assemble_sample(flavor, ["CfUnit"])
    for unit in result.units:
        total = sum(seg.count for seg in unit.segments)
        assert total == unit.text.count("\n")


def test_sourcemap_load_roundtrip(tmp_path: Path) -> None:
    result = assemble_sample(assemble.FLAVOR_IEC_CHECKER)
    assemble.write_result(result, str(tmp_path))
    loaded = assemble.SourceMap.load(str(tmp_path))
    direct = assemble.SourceMap.from_result(result)
    assert loaded.files == direct.files
    assert loaded.lookup("FB_Motor.st", 7) == ("src/POUs/Devices/FB_Motor/FB_Motor.decl.st", 7)
    assert loaded.main_source("FB_Motor.st") == "src/POUs/Devices/FB_Motor/FB_Motor.decl.st"
    assert loaded.lookup("Unknown.st", 1) is None
    assert assemble.SourceMap.load(str(tmp_path / "nothing")).files == {}


# ---------------------------------------------------------------------------
# Командная строка и ошибки
# ---------------------------------------------------------------------------


def test_cli_writes_outputs(sample_copy: Path) -> None:
    code = assemble.main(["--root", str(sample_copy), "--tests", "-q"])
    assert code == 0
    out = sample_copy / "build" / "assembled"
    assert (out / "all.st").is_file() and (out / "FB_F_Clamp_Test.st").is_file()
    data = json.loads((out / assemble.SOURCEMAP_FILE).read_text(encoding="utf-8"))
    assert data["flavor"] == "iec" and "FB_Motor.st" in data["files"]
    code = assemble.main(["--root", str(sample_copy), "--flavor", "rusty", "-q"])
    assert code == 0
    assert (out / "rusty" / "__RustyCompat.st").is_file()
    assert not (out / "rusty" / "FB_F_Clamp_Test.st").exists()


def test_cli_removes_stale_outputs(sample_copy: Path) -> None:
    out = sample_copy / "out"
    out.mkdir()
    (out / "FB_Old.st").write_text("x\n", encoding="utf-8")
    (out / "keep.txt").write_text("x\n", encoding="utf-8")
    assert assemble.main(["--root", str(sample_copy), "--out", str(out), "-q"]) == 0
    assert not (out / "FB_Old.st").exists()
    assert (out / "keep.txt").exists()


def test_cli_check_only_writes_nothing(sample_copy: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert assemble.main(["--root", str(sample_copy), "--check-only"]) == 0
    assert not (sample_copy / "build").exists()
    assert "проверено" in capsys.readouterr().out


def test_cli_layout_error_exit_code(make_tree: MakeTree, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_tree(
        {
            "src/POUs/FB_A/FB_A.decl.st": "FUNCTION_BLOCK FB_B\n",
            "src/POUs/FB_A/FB_A.impl.st": ";\n",
        }
    )
    assert assemble.main(["--root", str(root)]) == 1
    err = capsys.readouterr().err
    assert "src/POUs/FB_A/FB_A.decl.st:1: LAY002" in err
    assert not (root / "build").exists()


def test_cross_subdir_duplicate(make_tree: MakeTree) -> None:
    pou = {"FB_A.decl.st": "FUNCTION_BLOCK FB_A\n", "FB_A.impl.st": ";\n"}
    files = {f"src/POUs/FB_A/{k}": v for k, v in pou.items()}
    files.update({f"tests/POUs/FB_A/{k}": v for k, v in pou.items()})
    root = make_tree(files)
    code, result = assemble.run(str(root), "src", "tests", check_only=True)
    assert code == 1
    assert [(i.code, i.path) for i in result.errors] == [("LAY006", "tests/POUs/FB_A/FB_A.decl.st")]


def test_tests_dir_must_be_next_to_src(sample_copy: Path) -> None:
    assert assemble.main(["--root", str(sample_copy), "--tests", "--tests-dir", "/elsewhere/tests"]) == 2


def fb(name: str, extends: str = "") -> dict[str, str]:
    ext = f" EXTENDS {extends}" if extends else ""
    return {
        f"src/POUs/{name}/{name}.decl.st": f"FUNCTION_BLOCK {name}{ext}\n",
        f"src/POUs/{name}/{name}.impl.st": ";\n",
    }


def test_inheritance_order(make_tree: MakeTree) -> None:
    root = make_tree({**fb("FB_A", "FB_C"), **fb("FB_B"), **fb("FB_C", "FB_B"), **fb("FB_D", "Lib.FB_X")})
    code, result = assemble.run(str(root), check_only=True)
    assert code == 0
    assert [u.name for u in result.units] == ["FB_B", "FB_C", "FB_A", "FB_D"]


def test_inheritance_cycle(make_tree: MakeTree) -> None:
    root = make_tree({**fb("FB_A", "FB_B"), **fb("FB_B", "FB_A"), **fb("FB_C")})
    code, result = assemble.run(str(root), check_only=True)
    assert code == 1
    assert sorted(i.code for i in result.errors) == ["ASM001", "ASM001"]


def test_unknown_flavor() -> None:
    with pytest.raises(ValueError):
        assemble.assemble_objects([], "pascal")


# ---------------------------------------------------------------------------
# Вариант iec: сборка объектов
# ---------------------------------------------------------------------------


def unit_text(flavor: str, name: str, namespaces: list[str] | None = None) -> str:
    result = assemble_sample(flavor, namespaces)
    return next(u.text for u in result.units if u.name == name)


def test_iec_fb_layout() -> None:
    text = unit_text(assemble.FLAVOR_IEC, "FB_DeviceBase")
    order = [
        "FUNCTION_BLOCK ABSTRACT FB_DeviceBase IMPLEMENTS I_Device",
        "METHOD PUBLIC Reset : BOOL",
        "END_METHOD",
        "METHOD PUBLIC ABSTRACT Start",
        "PROPERTY_GET PUBLIC Mode : E_DeviceMode",
        "Mode := eModeInt;",
        "PROPERTY_SET PUBLIC Mode : E_DeviceMode",
        "eModeInt := Mode;",
        "// Общего тела нет",
        "END_FUNCTION_BLOCK",
    ]
    positions = [text.index(piece) for piece in order]
    assert positions == sorted(positions)
    assert text.count("END_PROPERTY") == 2
    assert text.endswith("END_FUNCTION_BLOCK\n")


def test_iec_interface_and_function() -> None:
    itf = unit_text(assemble.FLAVOR_IEC, "I_Device")
    assert "PROPERTY_GET Mode : E_DeviceMode\nEND_PROPERTY\nPROPERTY_SET Mode : E_DeviceMode\nEND_PROPERTY" in itf
    assert itf.endswith("END_INTERFACE\n")
    func = unit_text(assemble.FLAVOR_IEC, "F_Clamp")
    assert func.endswith("END_IF\nEND_FUNCTION\n")
    prg = unit_text(assemble.FLAVOR_IEC, "PRG_Main")
    assert prg.endswith("END_PROGRAM\n")


# ---------------------------------------------------------------------------
# Вариант rusty: правила замен
# ---------------------------------------------------------------------------


def rusty(text: str, ctx: F.Context | None = None) -> str:
    return F.rusty_text(text, ctx or F.Context())


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("IF itfNext <> 0 THEN", "IF __ItfIsSet(ADR(itfNext)) THEN"),
        ("IF itfNext = 0 THEN", "IF (NOT __ItfIsSet(ADR(itfNext))) THEN"),
        ("IF 0 <> itfNext THEN", "IF __ItfIsSet(ADR(itfNext)) THEN"),
        ("IF THIS^.itfNext <> 0 THEN", "IF __ItfIsSet(ADR(THIS^.itfNext)) THEN"),
        ("x := stCfg.itfDrive = 0 AND y;", "x := (NOT __ItfIsSet(ADR(stCfg.itfDrive))) AND y;"),
        ("IF a AND itfA <> 0 THEN", "IF a AND __ItfIsSet(ADR(itfA)) THEN"),
        ("IF iCount <> 0 THEN", "IF iCount <> 0 THEN"),
        ("IF itfA <> 0.5 THEN", "IF itfA <> 0.5 THEN"),
        ("IF itfA.iX <> 0 THEN", "IF itfA.iX <> 0 THEN"),
        ("IF aItf[1] <> 0 THEN", "IF aItf[1] <> 0 THEN"),
    ],
)
def test_rusty_itf_null_checks(source: str, expected: str) -> None:
    ctx = F.Context()
    assert rusty(source, ctx) == expected
    assert ctx.used_itf_helper == (expected != source)


def test_rusty_helper_emitted_once() -> None:
    result = assemble_sample(assemble.FLAVOR_RUSTY, ["CfUnit"])
    assert result.units[0].name == assemble.COMPAT_UNIT
    assert result.all_unit.text.count("FUNCTION __ItfIsSet") == 1
    assert sum(u.text.count("FUNCTION __ItfIsSet") for u in result.units) == 1


def test_rusty_helper_absent_without_checks(make_tree: MakeTree) -> None:
    root = make_tree(fb("FB_A"))
    code, result = assemble.run(str(root), flavor=assemble.FLAVOR_RUSTY, check_only=True)
    assert code == 0 and [u.name for u in result.units] == ["FB_A"]


def test_rusty_strip_namespaces_and_gvl_qualifiers() -> None:
    ctx = F.Context(gvl_names={"gvl_const"}, strip_namespaces=["CfUnit", "PL"])
    source = (
        "FUNCTION_BLOCK FB_T EXTENDS CfUnit.FB_TestSuite\n"
        "x := GVL_Const.MAX + PL.F_Lim(1) + cfunit.TEST_FINISHED() + st.GVL_Const.y;\n"
    )
    assert rusty(source, ctx) == (
        "FUNCTION_BLOCK FB_T EXTENDS FB_TestSuite\nx := MAX + F_Lim(1) + TEST_FINISHED() + st.GVL_Const.y;\n"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("xQ S= fbR.Q;", "IF fbR.Q THEN xQ := TRUE; END_IF;"),
        ("stX.aY[i].xZ R= a OR\n    b;", "IF a OR\n    b THEN stX.aY[i].xZ := FALSE; END_IF;"),
        ("IF S = 1 THEN", "IF S = 1 THEN"),
        ("IF x THEN y S= z; END_IF", "IF x THEN IF z THEN y := TRUE; END_IF; END_IF"),
    ],
)
def test_set_reset_assignments(source: str, expected: str) -> None:
    assert rusty(source) == expected


def test_rusty_declaration_rewrites() -> None:
    source = (
        'VAR_GLOBAL PERSISTENT RETAIN\n    s : STRING(80);\n    w : WSTRING(20) := "x";\nEND_VAR\n'
        "METHOD M\nVAR_INST\n    i : INT;\nEND_VAR\nVAR_STAT\n    j : INT;\nEND_VAR\n"
        "VAR\n    fbC : CTU;\n    aC : ARRAY[1..2] OF CTD;\nEND_VAR\nx := __ISVALIDREF(refX);\n"
    )
    assert rusty(source) == (
        'VAR_GLOBAL RETAIN\n    s : STRING[80];\n    w : WSTRING[20] := "x";\nEND_VAR\n'
        "METHOD M\nVAR\n    i : INT;\nEND_VAR\nVAR\n    j : INT;\nEND_VAR\n"
        "VAR\n    fbC : CDS_CTU;\n    aC : ARRAY[1..2] OF CDS_CTD;\nEND_VAR\nx := (ADR(refX) <> 0);\n"
    )


def test_rusty_union_and_struct_extends() -> None:
    text = unit_text(assemble.FLAVOR_RUSTY, "ST_MotorSts", ["CfUnit"])
    assert "EXTENDS" not in text
    assert "STRUCT eMode : E_DeviceMode; eNamur : E_NamurStatus; xFault : BOOL;\n" in text
    assert text.count("\n") == (SAMPLE / "src/DUTs/Motor/ST_MotorSts.dut.st").read_text(encoding="utf-8").count("\n")
    union = unit_text(assemble.FLAVOR_RUSTY, "U_RawValue", ["CfUnit"])
    assert "UNION" not in union and "END_STRUCT" in union


def test_rusty_struct_extends_chain_and_unknown_base() -> None:
    ctx = F.Context(struct_members={"st_a": (["a : INT;"], []), "st_b": (["b : INT;"], ["ST_A"])})
    text = "TYPE ST_C EXTENDS ST_B :\nSTRUCT\n    c : INT;\nEND_STRUCT\nEND_TYPE\n"
    assert rusty(text, ctx) == "TYPE ST_C :\nSTRUCT a : INT; b : INT;\n    c : INT;\nEND_STRUCT\nEND_TYPE\n"
    unknown = "TYPE ST_D EXTENDS Lib.ST_X :\nSTRUCT\n    d : INT;\nEND_STRUCT\nEND_TYPE\n"
    assert rusty(unknown, ctx) == unknown


def test_rusty_property_modifiers_removed() -> None:
    text = unit_text(assemble.FLAVOR_RUSTY, "FB_Motor", ["CfUnit"])
    assert "PROPERTY_GET Running : BOOL" in text
    assert "PROPERTY_GET PUBLIC" not in text
    assert "iStep : INT := STEP_IDLE;" in text


# ---------------------------------------------------------------------------
# Вариант iec-checker: понижение
# ---------------------------------------------------------------------------


def lower(text: str, ctx: F.Context | None = None) -> str:
    return F.iec_checker_text(text, ctx or F.Context())


def test_iec_checker_removes_pragmas_and_keeps_lines() -> None:
    source = "{attribute 'qualified_only'}\n{attribute 'x' := '1\n2'}\nTYPE E_A :\n(\n    A\n) INT;\nEND_TYPE\n"
    lowered = lower(source)
    assert "{" not in lowered and lowered.count("\n") == source.count("\n")
    assert ") ;" in lowered


def test_iec_checker_statement_rewrites() -> None:
    source = (
        "refCmd REF= stCmd;\npSts^.x := THIS^.y + SUPER^.z;\nx := __QUERYINTERFACE(a, b);\n"
        's := \'a b$$c\'; w := "Мотор $"q";\n/* c-коммент *) */\n'
    )
    assert lower(source) == (
        "refCmd := ADR(stCmd);\npSts.x := y + z;\nx := CDS__QUERYINTERFACE(a, b);\n"
        "s := 'a$20b$24c'; w := \"$041C$043E$0442$043E$0440$0020$0022q\";\n(* c-коммент * ) *)\n"
    )


def test_iec_checker_declaration_rewrites() -> None:
    source = (
        "VAR\n    p : POINTER TO INT;\n    r : REFERENCE TO REAL;\n    i : INT(0..100) := 5;\n"
        "    e : E_Mode := E_Mode.Auto;\n    t : TIME := T#5S;\n    a : ARRAY[0..2] OF INT := [1, -2, 3];\n"
        "    b : ARRAY[0..2] OF INT := [3(0)];\n    fbT : TON := (PT := T#1S);\n    k : INT := GVL_C.MAX;\n"
        "    x : BOOL := TRUE;\nEND_VAR\nVAR_IN_OUT\n    aV : ARRAY[*] OF REAL;\nEND_VAR\n"
    )
    assert lower(source) == (
        "VAR\n    p : REF_TO INT;\n    r : REF_TO REAL;\n    i : INT := 5;\n"
        "    e : E_Mode;\n    t : TIME := T#5S;\n    a : ARRAY[0..2] OF INT := [1, -2, 3];\n"
        "    b : ARRAY[0..2] OF INT;\n    fbT : TON;\n    k : INT;\n"
        "    x : BOOL := TRUE;\nEND_VAR\nVAR_IN_OUT\n    aV : ARRAY[0..0] OF REAL;\nEND_VAR\n"
    )


def test_iec_checker_struct_lowering() -> None:
    ctx = F.Context(struct_members={"st_base": (["b : INT;"], [])})
    source = (
        "TYPE ST_X EXTENDS ST_Base :\nSTRUCT\n    a : ARRAY[1..3] OF E_X; // c\n    e : E_X := E_X.A;\n"
        "END_STRUCT\nEND_TYPE\n"
    )
    assert lower(source, ctx) == (
        "TYPE ST_X :\nSTRUCT b : INT;\n    a : E_X; // c\n    e : E_X;\nEND_STRUCT\nEND_TYPE\n"
    )


def test_iec_checker_case_labels() -> None:
    ctx = F.Context(enum_values={"e_mode": {"auto": 0, "manual": 1}}, gvl_int_constants={"gvl_c": {"step": 10}})
    source = (
        "CASE e OF\n    E_Mode.Auto, E_Mode.Manual:\n        x := E_Mode.Auto;\n"
        "    GVL_C.STEP:\n        ;\n    Lib.E_Y.Z:\n        y := 1;\nEND_CASE\n"
    )
    assert lower(source, ctx) == (
        "CASE e OF\n    0, 1:\n        x := E_Mode.Auto;\n    10:\n"
        "        ;\n    Lib.E_Y.Z:\n        y := 1;\nEND_CASE\n"
    )


def test_context_enum_values_and_constants() -> None:
    objects = L.scan(str(SAMPLE), "src").objects
    ctx = F.Context.from_objects(objects)
    assert ctx.enum_values["e_devicemode"] == {"auto": 0, "manual": 1, "local": 2, "outofservice": 3}
    assert ctx.enum_values["e_namurstatus"]["failure"] == 4
    assert ctx.gvl_int_constants["gvl_const"] == {"step_idle": 0, "step_run": 10}
    assert ctx.gvl_names == {"gvl_const", "gvl_io", "pvl_retain"}


@pytest.mark.parametrize(
    ("literal", "value"),
    [("10", 10), ("-3", -3), ("16#FF", 255), ("2#1010", 10), ("INT#5", 5), ("1_000", 1000), ("1.5", None), ("X", None)],
)
def test_parse_int_literal(literal: str, value: int | None) -> None:
    assert F.parse_int_literal(literal) == value


def test_iec_checker_methods_become_functions() -> None:
    text = unit_text(assemble.FLAVOR_IEC_CHECKER, "FB_Motor")
    assert "FUNCTION_BLOCK FB_Motor\n" in text
    assert "METHOD" not in text and "PROPERTY" not in text
    reset = text[text.index("FUNCTION FB_Motor__Reset : BOOL") :]
    reset = reset[: reset.index("END_FUNCTION") + len("END_FUNCTION")]
    assert "VAR (* копии переменных FB_Motor" in reset
    assert "    itfInterlock : I_Resettable;" in reset
    assert "    Reset : BOOL;" in reset
    assert "Reset := FB_DeviceBase__Reset(xForce := xForce);" in reset
    assert reset.rstrip().endswith("FB_Motor__Reset := Reset;\nEND_FUNCTION")
    start = text[text.index("FUNCTION FB_Motor__Start : BOOL") :]
    assert "    stSts : ST_MotorSts;" in start.split("END_VAR")[1]
    assert "FUNCTION FB_Motor__Running__get : BOOL" in text


def test_iec_checker_inherited_vars_and_accessors() -> None:
    text = unit_text(assemble.FLAVOR_IEC_CHECKER, "FB_DeviceBase")
    assert "FUNCTION_BLOCK FB_DeviceBase\n" in text
    assert "FUNCTION FB_DeviceBase__Start : BOOL" in text
    assert "FUNCTION FB_DeviceBase__Mode__get : E_DeviceMode" in text
    setter = text[text.index("FUNCTION FB_DeviceBase__Mode__set : BOOL") :]
    assert "VAR_INPUT\n    Mode : E_DeviceMode;\nEND_VAR" in setter
    assert "    eModeInt : E_DeviceMode;" in setter


def test_iec_checker_interface_and_gvl() -> None:
    itf = unit_text(assemble.FLAVOR_IEC_CHECKER, "I_Device")
    assert "METHOD Mode__get : E_DeviceMode\nEND_METHOD" in itf
    assert "METHOD Mode__set\nVAR_INPUT\n    Mode : E_DeviceMode;\nEND_VAR\nEND_METHOD" in itf
    gvl = unit_text(assemble.FLAVOR_IEC_CHECKER, "GVL_Const")
    assert gvl.startswith("CONFIGURATION GVL_Const\n") and gvl.endswith("END_CONFIGURATION\n")
    pvl = unit_text(assemble.FLAVOR_IEC_CHECKER, "PVL_Retain")
    assert "VAR_GLOBAL RETAIN" in pvl


def test_iec_checker_function_without_return_type_gets_bool(make_tree: MakeTree) -> None:
    root = make_tree(
        {
            "src/POUs/F_X/F_X.decl.st": "FUNCTION F_X\nVAR_INPUT\n    iA : INT;\nEND_VAR\n",
            "src/POUs/F_X/F_X.impl.st": "iA := iA;\n",
        }
    )
    code, result = assemble.run(str(root), flavor=assemble.FLAVOR_IEC_CHECKER, check_only=True)
    assert code == 0
    assert result.units[0].text.startswith("FUNCTION F_X : BOOL\n")


def test_edits_preserve_newlines() -> None:
    text = "a\n{p\nq}\nb\n"
    tokens = L.tokenize(text)
    edits = F.Edits(text, tokens)
    pragma = next(i for i, t in enumerate(tokens) if t.kind == L.TK_PRAGMA)
    edits.replace(pragma, pragma, "")
    edits.replace(pragma, pragma, "ignored overlapping edit")
    assert edits.apply() == "a\n\n\nb\n"


def test_edit_header() -> None:
    text = "// c\nMETHOD PUBLIC Run\nVAR_INPUT\nEND_VAR\n"
    lowered = F.edit_header(text, keyword="FUNCTION", name="FB_X__Run", drop_modifiers=True, default_return_type="BOOL")
    assert lowered == ("// c\nFUNCTION FB_X__Run : BOOL\nVAR_INPUT\nEND_VAR\n")
    fb_text = "FUNCTION_BLOCK FINAL FB_A EXTENDS FB_B IMPLEMENTS I_A, I_B\nVAR\nEND_VAR\n"
    assert F.edit_header(fb_text, drop_modifiers=True, drop_extends=True, drop_implements=True) == (
        "FUNCTION_BLOCK FB_A\nVAR\nEND_VAR\n"
    )
    assert F.edit_header("x := 1;\n", keyword="FUNCTION") == "x := 1;\n"


def test_written_files_are_utf8_lf(tmp_path: Path) -> None:
    result = assemble_sample(assemble.FLAVOR_IEC)
    assemble.write_result(result, str(tmp_path))
    for name in os.listdir(tmp_path):
        data = (tmp_path / name).read_bytes()
        assert b"\r" not in data and not data.startswith(b"\xef\xbb\xbf")
