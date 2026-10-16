"""Тесты tools/codesys/stlayout.py: лексер, разбор объявлений, обход, проверки, запись."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import stlayout as L
from conftest import SAMPLE, MakeTree, write_tree

BOM = chr(0xFEFF)


def files_of(root: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            full = Path(dirpath) / name
            result[full.relative_to(root).as_posix()] = full.read_bytes()
    return result


# ---------------------------------------------------------------------------
# Нормализация
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("   \n\n\t\n", ""),
        ("A\n", "A\n"),
        ("A", "A\n"),
        ("A\n\n\n", "A\n"),
        ("A  \r\nB\t\r\n", "A\nB\n"),
        ("A\rB\r", "A\nB\n"),
        (BOM + "X\n", "X\n"),
        ("\n\nX\n", "\n\nX\n"),
        ("\tX\n", "\tX\n"),
    ],
)
def test_normalize_text(raw: str, expected: str) -> None:
    assert L.normalize_text(raw) == expected


@settings(max_examples=200)
@given(st.text(alphabet=st.sampled_from([*list("ab \t\r\n"), BOM, "я"]), max_size=60))
def test_normalize_is_idempotent(text: str) -> None:
    once = L.normalize_text(text)
    assert L.normalize_text(once) == once
    assert "\r" not in once
    assert once == "" or (once.endswith("\n") and not once.endswith("\n\n"))


# ---------------------------------------------------------------------------
# Лексер
# ---------------------------------------------------------------------------

ST_ALPHABET = [*list("abcXYZ_019 \t\n:=<>()[]{};,.^#$%'\"*/+-"), "(*", "*)", "//", "T#", "я"]


@settings(max_examples=300)
@given(st.lists(st.sampled_from(ST_ALPHABET), max_size=80).map("".join))
def test_tokenize_is_lossless(text: str) -> None:
    tokens = L.tokenize(text)
    assert "".join(t.text for t in tokens) == text
    for tok in tokens:
        assert text[tok.pos : tok.end] == tok.text
        assert tok.line == text.count("\n", 0, tok.pos) + 1


def test_tokenize_lossless_on_sample() -> None:
    for path in SAMPLE.rglob("*.st"):
        text = path.read_text(encoding="utf-8")
        assert "".join(t.text for t in L.tokenize(text)) == text


def kinds(text: str) -> list[tuple[str, str]]:
    return [(t.kind, t.text) for t in L.tokenize(text) if t.kind != L.TK_WS]


def test_tokenize_comments_and_pragmas() -> None:
    text = "a (* x (* nested *) y *) b // line\n{attribute 'x'} c /* c */ d"
    assert kinds(text) == [
        ("ident", "a"),
        ("comment", "(* x (* nested *) y *)"),
        ("ident", "b"),
        ("comment", "// line"),
        ("pragma", "{attribute 'x'}"),
        ("ident", "c"),
        ("comment", "/* c */"),
        ("ident", "d"),
    ]


def test_tokenize_unterminated_comment_runs_to_end() -> None:
    assert kinds("a (* open") == [("ident", "a"), ("comment", "(* open")]


def test_tokenize_strings_with_escapes() -> None:
    assert kinds("s := 'it$'s'; w := \"a$\"b\";") == [
        ("ident", "s"),
        ("op", ":="),
        ("string", "'it$'s'"),
        ("op", ";"),
        ("ident", "w"),
        ("op", ":="),
        ("wstring", '"a$"b"'),
        ("op", ";"),
    ]


def test_tokenize_literals() -> None:
    text = "T#1s500ms TIME#-5s DT#2020-01-01-12:00:00 INT#5 E_Mode#Auto 16#FF 1.5E-3 1_000 1..10 x.3 %IX0.0"
    assert [(k, v) for k, v in kinds(text)] == [
        ("typed", "T#1s500ms"),
        ("typed", "TIME#-5s"),
        ("typed", "DT#2020-01-01-12:00:00"),
        ("typed", "INT#5"),
        ("typed", "E_Mode#Auto"),
        ("number", "16#FF"),
        ("number", "1.5E-3"),
        ("number", "1_000"),
        ("number", "1"),
        ("op", ".."),
        ("number", "10"),
        ("ident", "x"),
        ("op", "."),
        ("number", "3"),
        ("address", "%IX0.0"),
    ]


def test_tokenize_non_ascii_identifier() -> None:
    assert kinds("xПуск := 1;")[0] == ("ident", "xПуск")


def test_strip_comments_keeps_positions() -> None:
    text = "a (* x\ny *) b {p} // c\nd"
    stripped = L.strip_comments(text)
    assert len(stripped) == len(text)
    assert stripped.count("\n") == text.count("\n")
    assert stripped.split() == ["a", "b", "d"]


# ---------------------------------------------------------------------------
# Заголовки и объявления
# ---------------------------------------------------------------------------


def test_parse_header_skips_comments_and_pragmas() -> None:
    text = (
        "(* FUNCTION_BLOCK Fake (* вложенный *) *)\n"
        "// PROGRAM AlsoFake\n"
        "{attribute 'reflection'}\n"
        "FUNCTION_BLOCK ABSTRACT FB_A EXTENDS CfUnit.FB_TestSuite IMPLEMENTS I_A, Lib.I_B // x\n"
        "VAR\nEND_VAR\n"
    )
    hdr = L.parse_header(text)
    assert hdr is not None
    assert (hdr.keyword, hdr.name, hdr.line) == ("FUNCTION_BLOCK", "FB_A", 4)
    assert hdr.modifiers == ["ABSTRACT"]
    assert hdr.extends == ["CfUnit.FB_TestSuite"]
    assert hdr.implements == ["I_A", "Lib.I_B"]


@pytest.mark.parametrize(
    ("text", "keyword", "name", "ret", "mods"),
    [
        ("FUNCTION F_X : REAL\nVAR_INPUT\nEND_VAR\n", "FUNCTION", "F_X", "REAL", []),
        ("METHOD PUBLIC Reset : STRING(80) // c\nVAR_INPUT\n", "METHOD", "Reset", "STRING(80)", ["PUBLIC"]),
        ("METHOD PRIVATE FINAL Start\nVAR_INPUT\nEND_VAR\n", "METHOD", "Start", None, ["PRIVATE", "FINAL"]),
        ("PROPERTY PUBLIC Count : INT\n", "PROPERTY", "Count", "INT", ["PUBLIC"]),
        ("PROPERTY Data : POINTER TO ST_X\n", "PROPERTY", "Data", "POINTER TO ST_X", []),
        ("PROGRAM PRG_Main\nVAR\nEND_VAR\n", "PROGRAM", "PRG_Main", None, []),
        ("INTERFACE I_Dev EXTENDS I_A, I_B\n", "INTERFACE", "I_Dev", None, []),
        ("{attribute 'qualified_only'}\nVAR_GLOBAL CONSTANT\nEND_VAR\n", "VAR_GLOBAL", None, None, ["CONSTANT"]),
    ],
)
def test_parse_header_kinds(text: str, keyword: str, name: str | None, ret: str | None, mods: list[str]) -> None:
    hdr = L.parse_header(text)
    assert hdr is not None
    assert (hdr.keyword, hdr.name, hdr.return_type, hdr.modifiers) == (keyword, name, ret, mods)


def test_parse_header_none_for_other_text() -> None:
    assert L.parse_header("x := 1;") is None
    assert L.parse_header("(* только комментарий *)") is None


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("TYPE ST_A :\nSTRUCT\n    x : BOOL;\nEND_STRUCT\nEND_TYPE\n", "struct"),
        ("TYPE U_A :\nUNION\n    x : BOOL;\nEND_UNION\nEND_TYPE\n", "union"),
        ("TYPE E_A :\n(\n    A,\n    B\n);\nEND_TYPE\n", "enum"),
        ("TYPE T_A : REAL; END_TYPE\n", "alias"),
    ],
)
def test_type_kinds(text: str, kind: str) -> None:
    tdecl = L.parse_type_decl(text)
    assert tdecl is not None and tdecl.kind == kind


def test_parse_type_decl_enum_values_and_base() -> None:
    tdecl = L.parse_type_decl("TYPE E_X :\n(\n  A := 0,\n  B, // c\n  C := 16#10\n) INT;\nEND_TYPE\n")
    assert tdecl is not None
    assert [(n, v) for n, v, _ in tdecl.enum_values] == [("A", "0"), ("B", None), ("C", "16#10")]
    assert tdecl.enum_base_type == "INT"


def test_parse_type_decl_struct_members() -> None:
    text = (
        "TYPE ST_X EXTENDS ST_Y :\nSTRUCT\n"
        "    a, b : INT := 5; // c\n"
        "    c : ARRAY[1..2] OF REAL := [1.0, 2.0];\n"
        "    s : STRING(80);\n"
        "END_STRUCT\nEND_TYPE\n"
    )
    tdecl = L.parse_type_decl(text)
    assert tdecl is not None
    assert tdecl.header.extends == ["ST_Y"]
    assert [(m.name_list, m.type_text, m.init_text) for m in tdecl.members] == [
        (["a", "b"], "INT", "5"),
        (["c"], "ARRAY[1..2] OF REAL", "[1.0, 2.0]"),
        (["s"], "STRING(80)", None),
    ]


def test_parse_var_blocks() -> None:
    text = (
        "FUNCTION_BLOCK X\nVAR_INPUT\n    xIn AT %IX0.0 : BOOL;\n    {attribute 'hide'}\n"
        "    fbT : TON := (PT := T#5S);\nEND_VAR\nVAR CONSTANT\n    C_X : INT := 3;\nEND_VAR\n"
    )
    blocks = L.parse_var_blocks(text)
    assert [(b.keyword, b.modifiers) for b in blocks] == [("VAR_INPUT", []), ("VAR", ["CONSTANT"])]
    first = blocks[0].decls
    assert [(d.name_list, d.type_text, d.init_text, d.line) for d in first] == [
        (["xIn"], "BOOL", None, 3),
        (["fbT"], "TON", "(PT := T#5S)", 5),
    ]
    assert first[0].address_index is not None


def test_case_label_indices() -> None:
    text = (
        "CASE e OF\n    E_X.A, E_X.B:\n        x := 1;\n    3..5, -1:\n        IF y THEN z := 2; END_IF\n"
        "    GVL_C.STEP:\n        x := 3;\nELSE\n    x := 0;\nEND_CASE\n"
    )
    tokens = L.tokenize(text)
    labels = "".join(tokens[i].text for i in L.case_label_indices(tokens))
    assert labels == "E_X.A,E_X.B3..5,-1GVL_C.STEP"


# ---------------------------------------------------------------------------
# Обход раскладки
# ---------------------------------------------------------------------------


def test_scan_sample_objects_and_order() -> None:
    result = L.scan(str(SAMPLE), "src")
    assert result.issues == []
    assert [(o.kind, o.name, o.folder) for o in result.objects] == [
        ("dut", "E_DeviceMode", []),
        ("dut", "E_NamurStatus", []),
        ("dut", "U_RawValue", []),
        ("dut", "ST_DeviceSts", ["Motor"]),
        ("dut", "ST_MotorCmd", ["Motor"]),
        ("dut", "ST_MotorSts", ["Motor"]),
        ("gvl", "GVL_Const", []),
        ("gvl", "GVL_Io", []),
        ("pvl", "PVL_Retain", []),
        ("itf", "I_Device", []),
        ("itf", "I_Resettable", []),
        ("pou", "F_Clamp", []),
        ("pou", "PRG_Main", []),
        ("pou", "FB_DeviceBase", ["Devices"]),
        ("pou", "FB_Motor", ["Devices"]),
    ]
    motor = result.find("FB_Motor")
    assert motor is not None
    assert motor.pou_kind == L.POU_FUNCTION_BLOCK
    assert motor.extends == ["FB_DeviceBase"]
    assert [m.name for m in motor.methods] == ["Reset", "Start"]
    assert [p.name for p in motor.properties] == ["Running"]
    running = motor.properties[0]
    assert running.has_get and not running.has_set
    assert motor.main_path() == "src/POUs/Devices/FB_Motor/FB_Motor.decl.st"
    base = result.find("fb_devicebase")  # поиск без учёта регистра
    assert base is not None and base.methods[1].is_abstract and base.methods[1].impl is None
    device = result.find("I_Device")
    assert device is not None
    mode = device.properties[0]
    assert (mode.get_decl, mode.set_decl, mode.get_impl) == ("", "", None)
    assert mode.has_get and mode.has_set


def test_scan_missing_subdir_is_empty(tmp_path: Path) -> None:
    result = L.scan(str(tmp_path), "src")
    assert result.objects == [] and result.ok


def test_scan_ignores_dotfiles_and_markdown(make_tree: MakeTree) -> None:
    root = make_tree(
        {
            "src/DUTs/.gitkeep": "",
            "src/README.md": "# x\n",
            "src/POUs/README.md": "x\n",
            "src/DUTs/E_A.dut.st": "TYPE E_A :\n(\n    A\n);\nEND_TYPE\n",
        }
    )
    result = L.scan(str(root), "src")
    assert result.issues == []
    assert [o.name for o in result.objects] == ["E_A"]


POU_OK = {
    "src/POUs/FB_A/FB_A.decl.st": "FUNCTION_BLOCK FB_A\nVAR\n    iX : INT;\nEND_VAR\n",
    "src/POUs/FB_A/FB_A.impl.st": "iX := iX;\n",
}


def issues_of(root: Path, subdir: str = "src") -> list[tuple[str, str, int]]:
    return [(i.code, i.path, i.line) for i in L.scan(str(root), subdir).issues]


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        (
            {"src/POUs/FB_A/FB_A.decl.st": "// заголовок\nFUNCTION_BLOCK FB_B\nVAR\nEND_VAR\n"},
            ("LAY002", "src/POUs/FB_A/FB_A.decl.st", 2),
        ),
        (
            {"src/DUTs/ST_A.dut.st": "TYPE ST_B :\nSTRUCT\n    x : BOOL;\nEND_STRUCT\nEND_TYPE\n"},
            ("LAY002", "src/DUTs/ST_A.dut.st", 1),
        ),
        ({"src/POUs/FB_A/Foo.txt": "x\n"}, ("LAY001", "src/POUs/FB_A/Foo.txt", 1)),
        ({"src/DUTs/ST_A.st": "x\n"}, ("LAY001", "src/DUTs/ST_A.st", 1)),
        ({"src/POUs/FB_A/Run.method.impl.st": "x := 1;\n"}, ("LAY004", "src/POUs/FB_A/Run.method.impl.st", 1)),
        ({"src/POUs/FB_A/Run.method.decl.st": "METHOD Run\n"}, ("LAY003", "src/POUs/FB_A/Run.method.impl.st", 1)),
        ({"src/POUs/FB_A/Value.get.impl.st": "Value := 1;\n"}, ("LAY004", "src/POUs/FB_A/Value.get.impl.st", 1)),
        (
            {"src/POUs/FB_A/Value.prop.decl.st": "PROPERTY Value : INT\n"},
            ("LAY003", "src/POUs/FB_A/Value.prop.decl.st", 1),
        ),
        (
            {
                "src/POUs/FB_A/Value.prop.decl.st": "PROPERTY Value\n",
                "src/POUs/FB_A/Value.get.impl.st": "Value := 1;\n",
            },
            ("LAY009", "src/POUs/FB_A/Value.prop.decl.st", 1),
        ),
        (
            {"src/POUs/FB_A/Run.method.decl.st": "METHOD Walk\n", "src/POUs/FB_A/Run.method.impl.st": ";\n"},
            ("LAY002", "src/POUs/FB_A/Run.method.decl.st", 1),
        ),
        (
            {"src/POUs/FB_A/FB_A.decl.st": "FUNCTION_BLOCK FB_A\nVAR\nEND_VAR\nEND_FUNCTION_BLOCK\n"},
            ("LAY005", "src/POUs/FB_A/FB_A.decl.st", 4),
        ),
        ({"src/POUs/FB_A/FB_A.impl.st": "x := 1;\nEND_FUNCTION_BLOCK\n"}, ("LAY005", "src/POUs/FB_A/FB_A.impl.st", 2)),
        ({"src/POUs/FB_A/Sub/X.decl.st": "x\n"}, ("LAY008", "src/POUs/FB_A/Sub", 1)),
        ({"src/POUs/Loose.decl.st": "x\n"}, ("LAY008", "src/POUs/Loose.decl.st", 1)),
        ({"src/Other/x.st": "x\n"}, ("LAY008", "src/Other", 1)),
        ({"src/DUTs/Bad-Name.dut.st": "x\n"}, ("LAY010", "src/DUTs/Bad-Name.dut.st", 1)),
        ({"src/GVLs/GVL_X.gvl.st": "VAR\n    x : INT;\nEND_VAR\n"}, ("LAY009", "src/GVLs/GVL_X.gvl.st", 1)),
        (
            {"src/DUTs/ST_A.dut.st": "TYPE ST_A :\nSTRUCT\n    x : BOOL;\nEND_STRUCT\n"},
            ("LAY005", "src/DUTs/ST_A.dut.st", 1),
        ),
        (
            {
                "src/POUs/F_X/F_X.decl.st": "FUNCTION F_X : INT\n",
                "src/POUs/F_X/F_X.impl.st": "F_X := 1;\n",
                "src/POUs/F_X/M.method.decl.st": "METHOD M\n",
                "src/POUs/F_X/M.method.impl.st": ";\n",
            },
            ("LAY005", "src/POUs/F_X/F_X.decl.st", 1),
        ),
        (
            {"src/Interfaces/I_A/I_A.itf.st": "INTERFACE I_A\n", "src/Interfaces/I_A/M.method.impl.st": ";\n"},
            ("LAY001", "src/Interfaces/I_A/M.method.impl.st", 1),
        ),
        (
            {
                "src/POUs/Devices/FB_A/FB_A.decl.st": "FUNCTION_BLOCK FB_A\n",
                "src/POUs/Devices/FB_A/FB_A.impl.st": ";\n",
            },
            ("LAY006", "src/POUs/FB_A/FB_A.decl.st", 1),
        ),
    ],
)
def test_validation_issues(make_tree: MakeTree, extra: dict[str, str], expected: tuple[str, str, int]) -> None:
    root = make_tree({**POU_OK, **extra})
    assert expected in issues_of(root)


def test_missing_pou_impl(make_tree: MakeTree) -> None:
    root = make_tree({"src/POUs/FB_A/FB_A.decl.st": POU_OK["src/POUs/FB_A/FB_A.decl.st"]})
    assert issues_of(root) == [("LAY003", "src/POUs/FB_A/FB_A.impl.st", 1)]


def test_encoding_issue(tmp_path: Path) -> None:
    path = tmp_path / "src" / "DUTs" / "E_A.dut.st"
    path.parent.mkdir(parents=True)
    path.write_bytes("TYPE E_A : (A); END_TYPE // Пуск\n".encode("cp1251"))
    assert issues_of(tmp_path) == [("LAY007", "src/DUTs/E_A.dut.st", 1)]


def test_pvl_without_persistent_is_warning(make_tree: MakeTree) -> None:
    root = make_tree({"src/GVLs/PVL_X.pvl.st": "VAR_GLOBAL RETAIN\n    x : INT;\nEND_VAR\n"})
    result = L.scan(str(root), "src")
    assert [(i.code, i.severity) for i in result.issues] == [("LAY005", "warning")]
    assert result.ok


def test_abstract_method_without_impl_is_ok(make_tree: MakeTree) -> None:
    root = make_tree({**POU_OK, "src/POUs/FB_A/Run.method.decl.st": "METHOD PUBLIC ABSTRACT Run\n"})
    assert issues_of(root) == []


def test_member_name_collision(make_tree: MakeTree) -> None:
    root = make_tree(
        {
            **POU_OK,
            "src/POUs/FB_A/Run.method.decl.st": "METHOD Run\n",
            "src/POUs/FB_A/Run.method.impl.st": ";\n",
            "src/POUs/FB_A/run.prop.decl.st": "PROPERTY run : INT\n",
            "src/POUs/FB_A/run.get.impl.st": "run := 1;\n",
        }
    )
    assert ("LAY006", "src/POUs/FB_A", 1) in issues_of(root)


def test_scan_normalizes_texts(make_tree: MakeTree) -> None:
    root = make_tree({"src/DUTs/E_A.dut.st": BOM + "TYPE E_A :  \r\n(\r\n    A\r\n);\r\nEND_TYPE\r\n\r\n"})
    obj = L.scan(str(root), "src").objects[0]
    assert obj.decl == "TYPE E_A :\n(\n    A\n);\nEND_TYPE\n"


# ---------------------------------------------------------------------------
# Запись и цикл scan -> write
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("subdir", ["src", "tests"])
def test_roundtrip_is_byte_identical(tmp_path: Path, subdir: str) -> None:
    result = L.scan(str(SAMPLE), subdir)
    assert result.ok and result.objects
    written = L.write_objects(result.objects, str(tmp_path), subdir)
    original = {k: v for k, v in files_of(SAMPLE).items() if k.startswith(subdir + "/")}
    copy = files_of(tmp_path)
    assert copy == original
    assert sorted(written) == sorted(original)


def test_roundtrip_of_unnormalized_input_converges(tmp_path: Path) -> None:
    messy = {
        "src/POUs/FB_A/FB_A.decl.st": BOM + "FUNCTION_BLOCK FB_A  \r\nVAR\r\nEND_VAR",
        "src/POUs/FB_A/FB_A.impl.st": "x := 1;\t\n\n\n",
        "src/POUs/FB_A/V.prop.decl.st": "PROPERTY V : INT\r\n",
        "src/POUs/FB_A/V.get.impl.st": "V := 1;",
        "src/POUs/FB_A/V.get.decl.st": "",
    }
    first = write_tree(tmp_path / "a", messy)
    objects = L.scan(str(first), "src").objects
    L.write_objects(objects, str(tmp_path / "b"), "src")
    once = files_of(tmp_path / "b")
    assert once["src/POUs/FB_A/FB_A.decl.st"] == b"FUNCTION_BLOCK FB_A\nVAR\nEND_VAR\n"
    assert once["src/POUs/FB_A/V.get.decl.st"] == b""
    L.write_objects(L.scan(str(tmp_path / "b"), "src").objects, str(tmp_path / "c"), "src")
    assert files_of(tmp_path / "c") == once


def test_write_objects_clean_removes_stale_files(tmp_path: Path) -> None:
    objects = L.scan(str(SAMPLE), "src").objects
    stale = write_tree(tmp_path, {"src/POUs/FB_Old/FB_Old.decl.st": "x\n", "src/POUs/keep.md": "doc\n"})
    L.write_objects(objects, str(stale), "src", clean=True)
    assert not (tmp_path / "src" / "POUs" / "FB_Old").exists()
    assert (tmp_path / "src" / "POUs" / "keep.md").exists()
    assert files_of(tmp_path / "src" / "POUs") != {}


def test_write_objects_fixes_case_of_existing_paths(tmp_path: Path) -> None:
    """Объект переименован в IDE только регистром: экспорт не теряет файлы (Windows) и
    приводит имена каталога и файлов к новому имени."""
    old = write_tree(
        tmp_path,
        {
            "src/POUs/fb_example/fb_example.decl.st": "FUNCTION_BLOCK fb_example\n",
            "src/POUs/fb_example/fb_example.impl.st": "\n",
            "src/POUs/fb_example/reset.method.decl.st": "METHOD reset : BOOL\n",
            "src/POUs/fb_example/reset.method.impl.st": "reset := TRUE;\n",
        },
    )
    obj = L.StObject(L.KIND_POU, "FB_Example", "FUNCTION_BLOCK FB_Example\n", impl="", subdir="src")
    obj.methods.append(L.StMethod("Reset", "METHOD Reset : BOOL\n", "Reset := TRUE;\n"))
    L.write_objects([obj], str(old), "src", clean=True)
    assert files_of(tmp_path / "src") == {
        "POUs/FB_Example/FB_Example.decl.st": b"FUNCTION_BLOCK FB_Example\n",
        "POUs/FB_Example/FB_Example.impl.st": b"",
        "POUs/FB_Example/Reset.method.decl.st": b"METHOD Reset : BOOL\n",
        "POUs/FB_Example/Reset.method.impl.st": b"Reset := TRUE;\n",
    }
    result = L.scan(str(tmp_path), "src")
    assert result.ok, [i.format() for i in result.issues]


def test_object_files_for_programmatic_object() -> None:
    obj = L.StObject(L.KIND_POU, "FB_X", "FUNCTION_BLOCK FB_X\n", folder=["A", "B"], impl="", subdir="src")
    obj.methods.append(L.StMethod("M", "METHOD M\n", ";\n"))
    obj.properties.append(L.StProperty("P", "PROPERTY P : INT\n", get_impl="P := 1;\n"))
    assert [path for path, _ in L.object_files(obj)] == [
        "src/POUs/A/B/FB_X/FB_X.decl.st",
        "src/POUs/A/B/FB_X/FB_X.impl.st",
        "src/POUs/A/B/FB_X/M.method.decl.st",
        "src/POUs/A/B/FB_X/M.method.impl.st",
        "src/POUs/A/B/FB_X/P.prop.decl.st",
        "src/POUs/A/B/FB_X/P.get.impl.st",
    ]
    gvl = L.StObject(L.KIND_PVL, "PVL_X", "VAR_GLOBAL PERSISTENT\nEND_VAR\n", subdir="tests")
    assert gvl.main_path() == "tests/GVLs/PVL_X.pvl.st"
