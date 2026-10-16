"""Тесты tools/check/run_rusty.py: поиск компилятора, исключения, команда, разбор вывода."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

import run_rusty
from conftest import MakeTree, requires_rusty


def touch(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return str(path)


def test_find_compiler_explicit_and_env(tmp_path: Path) -> None:
    plc = touch(tmp_path / "bin" / "plc")
    assert run_rusty.find_compiler(plc, env={}) == plc
    assert run_rusty.find_compiler(None, env={"RUSTY_PLC": plc}) == plc
    with pytest.raises(run_rusty.ToolMissing):
        run_rusty.find_compiler(str(tmp_path / "missing"), env={})
    with pytest.raises(run_rusty.ToolMissing):
        run_rusty.find_compiler(None, env={"RUSTY_PLC": str(tmp_path / "missing")})


def test_find_compiler_path_and_known_location(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run_rusty.find_compiler(None, env={}, which=lambda name: "/usr/bin/plc") == "/usr/bin/plc"
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    with pytest.raises(run_rusty.ToolMissing):
        run_rusty.find_compiler(None, env={}, which=lambda name: None)
    known = os.path.expanduser(run_rusty.KNOWN_PLC)
    target = known + (".exe" if os.name == "nt" else "")
    touch(Path(target))
    assert run_rusty.find_compiler(None, env={}, which=lambda name: None) == target


def test_find_stdlib(tmp_path: Path) -> None:
    plc = touch(tmp_path / "rusty" / "plc")
    with pytest.raises(run_rusty.ToolMissing):
        run_rusty.find_stdlib(plc, env={})
    include = tmp_path / "rusty" / "stdlib" / "include"
    touch(include / "b.st")
    touch(include / "a.st")
    touch(include / "readme.txt")
    assert run_rusty.find_stdlib(plc, env={}) == [str(include / "a.st"), str(include / "b.st")]
    other = tmp_path / "other"
    touch(other / "x.st")
    assert run_rusty.find_stdlib(plc, env={"RUSTY_STDLIB_INCLUDE": str(other)}) == [str(other / "x.st")]
    with pytest.raises(run_rusty.ToolMissing):
        run_rusty.find_stdlib(plc, explicit=str(tmp_path / "none"), env={})
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(run_rusty.ToolMissing):
        run_rusty.find_stdlib(plc, explicit=str(empty), env={})


def test_read_exclude(tmp_path: Path) -> None:
    path = tmp_path / "exclude.txt"
    path.write_text("# комментарий\n\nFB_A.st  # нет объявлений SysCom\nFB_B # причина\n", encoding="utf-8")
    assert run_rusty.read_exclude(str(path)) == {"FB_A.st": "нет объявлений SysCom", "FB_B.st": "причина"}
    assert run_rusty.read_exclude(str(tmp_path / "none.txt")) == {}
    path.write_text("FB_C.st\n", encoding="utf-8")
    with pytest.raises(run_rusty.ExcludeError, match="нет причины"):
        run_rusty.read_exclude(str(path))


def test_repository_exclude_file_is_valid() -> None:
    run_rusty.read_exclude(run_rusty.DEFAULT_EXCLUDE)


def test_build_command() -> None:
    cmd = run_rusty.build_command("plc", ["a.st", "b.st"], ["std1.st"], ["shim.st"])
    assert cmd == ["plc", "--check", "a.st", "b.st", "-i", "std1.st", "-i", "shim.st", "--error-format", "clang"]


def test_parse_diagnostics() -> None:
    output = (
        "\\\\?\\C:\\build\\FB_A.st:78:4:{78:4-78:16}: error[E031]: Invalid expression\n"
        "/tmp/x/PRG_Main.st:3:1:{3:1-3:5}: warning[E049]: Illegal access to private member\n"
        "error: Compilation aborted due to critical errors\n"
        "FB_A.st:2:4:{2:4-2:17}: \n"
    )
    diags = run_rusty.parse_diagnostics(output)
    assert [(d.file, d.line, d.col, d.severity, d.code) for d in diags] == [
        ("FB_A.st", 78, 4, "error", "E031"),
        ("PRG_Main.st", 3, 1, "warning", "E049"),
    ]
    diags[0].source, diags[0].source_line = "src/POUs/FB_A/FB_A.impl.st", 5
    assert diags[0].format() == "src/POUs/FB_A/FB_A.impl.st:5:4: error[E031] Invalid expression (собрано: FB_A.st:78)"
    assert diags[1].format() == "PRG_Main.st:3:1: warning[E049] Illegal access to private member"


def test_optional_without_compiler(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def missing(*args: object, **kwargs: object) -> str:
        raise run_rusty.ToolMissing("нет plc")

    monkeypatch.setattr(run_rusty, "find_compiler", missing)
    assert run_rusty.main(["--optional"]) == 0
    assert "пропущена" in capsys.readouterr().out
    assert run_rusty.main([]) == 1


def test_bad_exclude_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_rusty, "find_compiler", lambda *a, **k: "plc")
    monkeypatch.setattr(run_rusty, "find_stdlib", lambda *a, **k: ["std.st"])
    bad = tmp_path / "exclude.txt"
    bad.write_text("FB_A.st\n", encoding="utf-8")
    assert run_rusty.main(["--exclude-file", str(bad)]) == 2


def test_main_with_fake_compiler(sample_copy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Без настоящего plc: проверяем состав команды, исключения и отчёты."""
    monkeypatch.setattr(run_rusty, "find_compiler", lambda *a, **k: "plc")
    monkeypatch.setattr(run_rusty, "find_stdlib", lambda *a, **k: ["std.st"])
    calls: list[list[str]] = []

    class Proc:
        returncode = 1
        stdout = "FB_Motor.st:7:4:{7:4-7:9}: error[E048]: Could not resolve reference to X\n"
        stderr = ""

    def fake_run(cmd: list[str], **kwargs: object) -> Proc:
        calls.append(cmd)
        return Proc()

    monkeypatch.setattr(subprocess, "run", fake_run)
    exclude = sample_copy / "exclude.txt"
    exclude.write_text("PRG_Tests.st  # проверяется отдельно\nFB_Gone.st  # объекта нет\n", encoding="utf-8")
    code = run_rusty.main(["--root", str(sample_copy), "--exclude-file", str(exclude)])
    assert code == 1
    cmd = calls[0]
    names = [os.path.basename(c) for c in cmd if c.endswith(".st")]
    assert "PRG_Tests.st" not in names and "all.st" not in names
    assert "FB_F_Clamp_Test.st" in names and "__RustyCompat.st" in names
    assert "cfunit.st" in names and "codesys_standard.st" in names and "std.st" in names
    report = json.loads((sample_copy / "build" / "rusty.json").read_text(encoding="utf-8"))
    assert report["errors"] == 1
    assert report["diagnostics"][0]["source"] == "src/POUs/Devices/FB_Motor/FB_Motor.decl.st"
    assert (sample_copy / "build" / "rusty.log").read_text(encoding="utf-8").startswith("plc --check")


@pytest.mark.integration
@requires_rusty
def test_integration_sample_passes(sample_copy: Path) -> None:
    assert run_rusty.main(["--root", str(sample_copy)]) == 0
    report = json.loads((sample_copy / "build" / "rusty.json").read_text(encoding="utf-8"))
    assert report["errors"] == 0 and report["returncode"] == 0


@pytest.mark.integration
@requires_rusty
def test_integration_error_is_mapped_to_source(make_tree: MakeTree) -> None:
    root = make_tree(
        {
            "src/POUs/F_X/F_X.decl.st": "FUNCTION F_X : INT\nVAR_INPUT\n    iA : INT;\nEND_VAR\n",
            "src/POUs/F_X/F_X.impl.st": "// тело\nF_X := iA + xUnknown;\n",
        }
    )
    assert run_rusty.main(["--root", str(root), "--no-tests"]) == 1
    report = json.loads((root / "build" / "rusty.json").read_text(encoding="utf-8"))
    errors = [d for d in report["diagnostics"] if d["severity"] == "error"]
    assert errors and errors[0]["source"] == "src/POUs/F_X/F_X.impl.st" and errors[0]["source_line"] == 2


@pytest.mark.integration
@requires_rusty
def test_integration_codesys_counter_shim(make_tree: MakeTree) -> None:
    root = make_tree(
        {
            "src/POUs/FB_C/FB_C.decl.st": "FUNCTION_BLOCK FB_C\nVAR\n    fbCnt : CTU;\n    xIn : BOOL;\nEND_VAR\n",
            "src/POUs/FB_C/FB_C.impl.st": "fbCnt(CU := xIn, RESET := FALSE, PV := 10);\nxIn := fbCnt.Q;\n",
        }
    )
    assert run_rusty.main(["--root", str(root), "--no-tests"]) == 0
