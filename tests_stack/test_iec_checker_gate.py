"""Обёртка статанализа tools_project/iec_checker_gate.py: понижение, проверка обращений, пробелы разборщика.

Заменяет для этого проекта интеграционный тест шаблона test_integration_repository_sources
(pyproject.toml, addopts): ПЛК-часть проверяется через обёртку, а не напрямую run_iec_checker.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

import iec_checker_gate as G
import run_iec_checker

REPO_ROOT = Path(__file__).resolve().parent.parent


def lower(text: str, constants: dict[str, int] | None = None) -> tuple[str, G.Lowering]:
    stats = G.Lowering()
    return G.lower_text(text, constants or {}, stats), stats


def test_lowering_substitutes_named_lengths_and_bounds() -> None:
    consts = {"GVL_Const.MQTT_TOPIC_LEN": 128, "POINT_COUNT": 121, "GVL_IiotMap.POINT_COUNT": 121}
    text, stats = lower(
        "    sTopic : STRING(80);\n"
        "    sT : STRING[GVL_Const.MQTT_TOPIC_LEN];\n"
        "    a : ARRAY[1..GVL_IiotMap.POINT_COUNT] OF INT;\n"
        "    b : ARRAY[0..POINT_COUNT - 1, 1..2] OF INT;\n"
        "    c : ARRAY[1..UNKNOWN_LEN] OF INT;\n",
        consts,
    )
    assert text.splitlines() == [
        "    sTopic : STRING(80);",
        "    sT : STRING[128];",
        "    a : ARRAY[1..121] OF INT;",
        "    b : ARRAY[0..120, 1..2] OF INT;",
        "    c : ARRAY[1..UNKNOWN_LEN] OF INT;",
    ]
    assert stats.constants == 3


def test_lowering_restores_semicolon_of_dropped_array_initializer() -> None:
    text, stats = lower("    POINT_CFG : ARRAY[1..3] OF ST_X\n\n\n;\n    N : INT := 1;\n")
    assert text.split("\n") == ["    POINT_CFG : ARRAY[1..3] OF ST_X;", "", "", "", "    N : INT := 1;", ""]
    assert stats.semicolons == 1
    with pytest.raises(ValueError):
        lower("    A : ARRAY[1..3] OF INT\n    B : INT;\n")


def test_lowering_short_circuit_and_field_after_index_outside_comments() -> None:
    text, stats = lower("IF x AND_THEN a[i].b.c > 0 OR_ELSE y THEN // a[i].b AND_THEN\n    a[1].d := s[2];\n")
    assert text.splitlines() == ["IF x AND a[i] > 0 OR y THEN // a[i].b AND_THEN", "    a[1] := s[2];"]
    assert (stats.short_circuit, stats.fields) == (2, 2)


def test_constants_from_sources_qualified_and_unambiguous_bare(tmp_path: Path) -> None:
    gvl = tmp_path / "GVL_Const.gvl.st"
    gvl.write_text(
        "VAR_GLOBAL CONSTANT\n    TOPIC_LEN : UINT := 128;\n    DUP : INT := 1;\nEND_VAR\n", encoding="utf-8"
    )
    fb = tmp_path / "FB_X.decl.st"
    fb.write_text("VAR CONSTANT\n    DUP : INT := 2;\n    LOCAL_MAX : UINT := 8;\nEND_VAR\n", encoding="utf-8")
    table = G.collect_constants([gvl, fb])
    assert table == {"GVL_Const.TOPIC_LEN": 128, "GVL_Const.DUP": 1, "TOPIC_LEN": 128, "LOCAL_MAX": 8}


def finding(source: str, var: str) -> run_iec_checker.Finding:
    return run_iec_checker.Finding(
        "UnusedVariable", f"Found unused local variable: {var}", "X.st", 1, 1, source=source, source_line=3
    )


def test_confirm_usage_finds_access_in_methods_and_own_body(tmp_path: Path) -> None:
    pou = tmp_path / "src" / "POUs" / "FB_A"
    pou.mkdir(parents=True)
    (pou / "FB_A.decl.st").write_text(
        "FUNCTION_BLOCK FB_A\nVAR\n    fbParser : FB_P;\n    xIdle : BOOL;\n", encoding="utf-8"
    )
    (pou / "FB_A.impl.st").write_text("// xIdle только в комментарии\ns := 'xIdle';\n", encoding="utf-8")
    (pou / "Run.method.decl.st").write_text("METHOD Run\nVAR\n    stCmd : ST_C;\n    xLost : BOOL;\n", encoding="utf-8")
    (pou / "Run.method.impl.st").write_text("(* stCmd\n *)\nfbParser.Parse();\nstCmd.xAck := TRUE;\n", encoding="utf-8")
    (pou / "Other.method.impl.st").write_text("xLost := TRUE;\n", encoding="utf-8")
    items = [
        finding("src/POUs/FB_A/FB_A.decl.st", "FBPARSER"),
        finding("src/POUs/FB_A/FB_A.decl.st", "XIDLE"),
        finding("src/POUs/FB_A/Run.method.decl.st", "STCMD"),
        finding("src/POUs/FB_A/Run.method.decl.st", "XLOST"),
    ]
    assert G.confirm_usage(items, tmp_path) == 2
    assert [f.status for f in items] == ["allowed", "error", "allowed", "error"]
    assert "src/POUs/FB_A/Run.method.impl.st:3" in items[0].reason
    assert "src/POUs/FB_A/Run.method.impl.st:4" in items[2].reason


def report(*findings: dict[str, Any], unused: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"findings": list(findings), "unused_allow": unused or [], "summary": {}}


def gap(file: str, match: str) -> G.Gap:
    return G.Gap(file, re.compile(match), "причина")


def test_gate_accepts_only_listed_parser_gaps(tmp_path: Path) -> None:
    src = tmp_path / "src" / "POUs" / "F_A"
    src.mkdir(parents=True)
    (src / "F_A.impl.st").write_text("x := 1;\nF_A := LTIME();\n", encoding="utf-8")
    known = {"id": "ParserError", "status": "error", "source": "src/POUs/F_A/F_A.impl.st", "source_line": 2}
    other = {"id": "ParserError", "status": "error", "source": "src/POUs/F_A/F_A.impl.st", "source_line": 1}
    gaps = [gap("src/POUs/F_A/F_A.impl.st", r"\bLTIME\(\)")]
    result = G.evaluate(report(known), gaps, tmp_path, True)
    assert result.ok and result.known[0]["line_text"] == "F_A := LTIME();"
    result = G.evaluate(report(other), [gap("src/POUs/F_A/F_A.impl.st", r"\bLTIME\(\)")], tmp_path, True)
    assert not result.ok and result.errors == [other] and len(result.stale_gaps) == 1


def test_gate_fails_on_unjustified_finding_and_unused_allow(tmp_path: Path) -> None:
    item = {"id": "PLCOPEN-L17", "status": "error", "source": "src/POUs/F_A/F_A.impl.st", "source_line": 3}
    assert G.evaluate(report(item), [], tmp_path, True).errors == [item]
    unused = [{"id": "X", "file": "src/*"}]
    assert not G.evaluate(report(unused=unused), [], tmp_path, True).ok
    assert G.evaluate(report(unused=unused), [], tmp_path, False).ok


def test_gate_without_tests_ignores_gaps_in_tests(tmp_path: Path) -> None:
    gaps = [gap("tests/POUs/FB_T/FB_T.impl.st", "x"), gap("src/POUs/F_A/F_A.impl.st", "y")]
    result = G.evaluate(report(), gaps, tmp_path, False)
    assert [g.file for g in result.stale_gaps] == ["src/POUs/F_A/F_A.impl.st"]
    assert len(G.evaluate(report(), gaps, tmp_path, True).stale_gaps) == 2


def test_gap_file_is_valid_and_points_to_existing_lines() -> None:
    gaps = G.load_gaps(G.DEFAULT_GAPS)
    assert gaps
    for item in gaps:
        text = (REPO_ROOT / item.file).read_text(encoding="utf-8")
        assert any(item.match.search(line) for line in text.splitlines()), item.file


def test_gate_rejects_bad_gap_file(tmp_path: Path) -> None:
    bad = tmp_path / "gaps.toml"
    bad.write_text('[[gap]]\nfile = "a"\nmatch = "("\nreason = "r"\n', encoding="utf-8")
    with pytest.raises(G.GapError):
        G.load_gaps(bad)
    bad.write_text('[[gap]]\nfile = "a"\nmatch = "x"\n', encoding="utf-8")
    with pytest.raises(G.GapError):
        G.load_gaps(bad)
    assert G.main(["--gaps", str(bad)]) == G.EXIT_CONFIG


def test_ci_runs_static_analysis_through_gate() -> None:
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "run: python tools_project/iec_checker_gate.py\n" in ci
    assert "run: python tools/check/run_iec_checker.py" not in ci


def _iec_checker_available() -> bool:
    try:
        run_iec_checker.find_binary()
    except run_iec_checker.ToolMissing:
        return False
    return True


@pytest.mark.integration
@pytest.mark.skipif(not _iec_checker_available(), reason="iec_checker не найден")
def test_repository_sources_pass_iec_checker_gate() -> None:
    """src/ и tests/ через обёртку: необоснованных нет, каждое обоснование и каждый пробел используются."""
    assert G.main(["--root", str(REPO_ROOT)]) == G.EXIT_OK
    summary = json.loads((REPO_ROOT / "build" / "iec_checker_gate.json").read_text(encoding="utf-8"))
    assert summary["ok"] and summary["errors"] == 0 and summary["unused_allow"] == []
    assert {g["source"] for g in summary["known_parser_gaps"]} == {g.file for g in G.load_gaps(G.DEFAULT_GAPS)}
