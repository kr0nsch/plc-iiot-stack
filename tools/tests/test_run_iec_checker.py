"""Тесты tools/check/run_iec_checker.py: поиск, команды, разбор, обоснования, отчёты."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import assemble
import run_iec_checker as R
from conftest import LOWERING, SAMPLE, SOURCEMAP, SOURCEMAP_CP8, MakeTree, requires_iec_checker, sourcemap_lines

ALLOW_SAMPLE = """
[[allow]]
id = "PLCOPEN-CP3"
file = "src/*"
reason = "значения по умолчанию типов"

[[allow]]
id = "PLCOPEN-CP3"
file = "tests/*"
reason = "то же для тестов"

[[allow]]
id = "PLCOPEN-L17"
file = "src/*"
reason = "ветка ELSE не нужна"

[[allow]]
id = "PLCOPEN-CP9"
file = "src/*"
reason = "завышенная метрика"

[[allow]]
id = "UnusedVariable"
file = "*"
reason = "v0.4 не считает вызов экземпляра и обращение к полям использованием"
"""


def test_find_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binary = tmp_path / "iec_checker"
    binary.write_text("", encoding="utf-8")
    assert R.find_binary(str(binary), env={}) == str(binary)
    assert R.find_binary(None, env={"IEC_CHECKER": str(binary)}) == str(binary)
    with pytest.raises(R.ToolMissing):
        R.find_binary(str(tmp_path / "none"), env={})
    seen: list[str] = []

    def which(name: str) -> str | None:
        seen.append(name)
        return "/usr/local/bin/iec_checker_Linux_x86_64" if name == "iec_checker_Linux_x86_64" else None

    assert R.find_binary(None, env={}, which=which) == "/usr/local/bin/iec_checker_Linux_x86_64"
    assert seen[:2] == ["iec_checker", "iec_checker_Linux_x86_64"]
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    with pytest.raises(R.ToolMissing):
        R.find_binary(None, env={}, which=lambda name: None)
    known = Path(os.path.expanduser(R.KNOWN_DIR)) / "iec_checker_Windows_x86_64.exe"
    known.parent.mkdir(parents=True)
    known.write_text("", encoding="utf-8")
    assert R.find_binary(None, env={}, which=lambda name: None) == str(known)


def test_build_command_local_and_docker(tmp_path: Path) -> None:
    target = tmp_path / "out" / "FB_A.st"
    assert R.build_command(str(target), binary="iec") == ["iec", "-o", "json", str(target)]
    cmd = R.build_command(str(target), docker_image="jubnzv1/iec-checker:nightly")
    assert cmd == [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{target.parent}:/work",
        "-w",
        "/work",
        "jubnzv1/iec-checker:nightly",
        "-o",
        "json",
        "FB_A.st",
    ]
    with pytest.raises(ValueError):
        R.build_command(str(target))


def test_parse_output() -> None:
    output = (
        "warning: something\n"
        '[{"linenr":3,"column":10,"file":"","id":"PLCOPEN-CP3","msg":"Variable X","type":["Inspection"]}]\n'
        '[{"linenr":0,"column":0,"file":"","id":"PLCOPEN-CP9","msg":"Code is too complex"}]\n'
        "[not json\n"
    )
    findings = R.parse_output(output, "FB_A.st")
    assert [(f.id, f.line, f.column, f.file) for f in findings] == [
        ("PLCOPEN-CP3", 3, 10, "FB_A.st"),
        ("PLCOPEN-CP9", 0, 0, "FB_A.st"),
    ]
    assert R.parse_output("[]\n", "X.st") == []
    broken = R.parse_output("Fatal error: exception Not_found\n", "X.st")
    assert [(f.id, f.file) for f in broken] == [("ToolError", "X.st")]


def test_load_allow(tmp_path: Path) -> None:
    path = tmp_path / "allow.toml"
    path.write_text(ALLOW_SAMPLE, encoding="utf-8")
    rules = R.load_allow(str(path))
    assert [(r.id, r.file) for r in rules][:2] == [("PLCOPEN-CP3", "src/*"), ("PLCOPEN-CP3", "tests/*")]
    assert all(r.checker == "" and r.applies_to("v0.4") and r.applies_to("nightly") for r in rules)
    assert R.load_allow(str(tmp_path / "none.toml")) == []
    path.write_text('[[allow]]\nid = "PLCOPEN-CP17"\nfile = "*"\nreason = "r"\nchecker = "nightly"\n', encoding="utf-8")
    [nightly] = R.load_allow(str(path))
    assert nightly.checker == "nightly" and nightly.applies_to("nightly") and not nightly.applies_to("v0.4")
    for bad in (
        '[[allow]]\nid = "X"\nfile = "*"\n',
        '[[allow]]\nid = "X"\nfile = "*"\nreason = "  "\n',
        '[[allow]]\nid = "X"\nfile = "*"\nreason = "r"\nmatch = "("\n',
        '[[allow]]\nid = "X"\nfile = "*"\nreason = "r"\nchecker = "v0.5"\n',
        "[[allow]\n",
    ):
        path.write_text(bad, encoding="utf-8")
        with pytest.raises(R.AllowError):
            R.load_allow(str(path))


def test_repository_allow_file_is_valid() -> None:
    assert all(rule.reason for rule in R.load_allow(R.DEFAULT_ALLOW))


def sample_sourcemap() -> assemble.SourceMap:
    objects, _ = assemble.load_objects(str(SAMPLE), ["src", "tests"])
    return assemble.SourceMap.from_result(assemble.assemble_objects(objects, assemble.FLAVOR_IEC_CHECKER))


def test_classify_statuses() -> None:
    smap = sample_sourcemap()
    rules = [
        R.AllowRule("PLCOPEN-CP3", "src/POUs/F_Clamp/*", "умолчания"),
        R.AllowRule("UnusedVariable", "PRG_Main.st", "ложное срабатывание", match="FBRUNEDGE"),
        R.AllowRule("ParserError", "*", "нельзя обосновать"),
        R.AllowRule("PLCOPEN-CP9", "src/POUs/Devices/FB_Motor/*", "метрика"),
    ]
    synthetic_line = 0
    for start, _, source, _ in smap.files["FB_Motor.st"]:
        if source is None and isinstance(start, int) and start > 1:
            synthetic_line = start
            break
    findings = [
        R.Finding("PLCOPEN-CP3", "Variable RVALUE", "F_Clamp.st", 9, 10),
        R.Finding("UnusedVariable", "unused FBRUNEDGE", "PRG_Main.st", 10, 13),
        R.Finding("UnusedVariable", "unused XINIT", "PRG_Main.st", 12, 9),
        R.Finding("ParserError", "", "FB_Motor.st", 30, 1),
        R.Finding("PLCOPEN-CP3", "copy", "FB_Motor.st", synthetic_line, 5),
        R.Finding("PLCOPEN-CP9", "Code is too complex", "FB_Motor.st", 0, 0),
    ]
    R.classify(findings, smap, rules)
    assert [f.status for f in findings] == ["allowed", "allowed", "error", "error", "artifact", "allowed"]
    assert findings[0].source == "src/POUs/F_Clamp/F_Clamp.decl.st" and findings[0].source_line == 9
    assert findings[5].source == "src/POUs/Devices/FB_Motor/FB_Motor.decl.st" and findings[5].source_line == 0
    assert [r.used for r in rules] == [1, 1, 0, 1]
    report = R.markdown_report(findings, rules, "iec_checker")
    assert "| необоснованные (error) | 2 |" in report
    assert "## Неиспользованные обоснования" in report and "`ParserError`" in report


def fake_checker(monkeypatch: pytest.MonkeyPatch, output_for: dict[str, str]) -> list[list[str]]:
    calls: list[list[str]] = []

    class Proc:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout
            self.stderr = ""
            self.returncode = 0

    def run(cmd: list[str], **kwargs: object) -> Proc:
        calls.append(cmd)
        return Proc(output_for.get(os.path.basename(cmd[-1]), "[]"))

    monkeypatch.setattr(R, "find_binary", lambda *a, **k: "iec_checker")
    monkeypatch.setattr(subprocess, "run", run)
    return calls


def test_main_with_fake_checker(sample_copy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    finding = '[{"linenr":9,"column":10,"file":"","id":"PLCOPEN-CP3","msg":"Variable RVALUE"}]'
    calls = fake_checker(monkeypatch, {"F_Clamp.st": finding})
    allow = sample_copy / "allow.toml"
    allow.write_text(ALLOW_SAMPLE, encoding="utf-8")
    assert R.main(["--root", str(sample_copy), "--allow", str(allow)]) == 0
    assert len(calls) == 15 and all(c[:3] == ["iec_checker", "-o", "json"] for c in calls)
    report = json.loads((sample_copy / "build" / "iec_checker.json").read_text(encoding="utf-8"))
    assert report["summary"] == {"error": 0, "allowed": 1, "artifact": 0}
    assert report["findings"][0]["source"] == "src/POUs/F_Clamp/F_Clamp.decl.st"
    assert (sample_copy / "build" / "iec_checker.md").read_text(encoding="utf-8").startswith("# Отчёт iec_checker")
    no_allow = sample_copy / "empty.toml"
    no_allow.write_text("", encoding="utf-8")
    assert R.main(["--root", str(sample_copy), "--allow", str(no_allow)]) == 1


def test_main_with_tests_and_docker(sample_copy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = fake_checker(monkeypatch, {})
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    assert R.main(["--root", str(sample_copy), "--tests", "--docker", "img:tag"]) == 0
    assert len(calls) == 17 and all(c[0] == "docker" and "img:tag" in c for c in calls)
    report = json.loads((sample_copy / "build" / "iec_checker.json").read_text(encoding="utf-8"))
    assert report["checker"] == "nightly"


ALLOW_BY_CHECKER = """
[[allow]]
id = "UnusedVariable"
file = "src/*"
reason = "только v0.4"
checker = "v0.4"

[[allow]]
id = "PLCOPEN-CP17"
file = "src/*"
reason = "только nightly"
checker = "nightly"
"""


@pytest.mark.parametrize(
    ("args", "checker", "allowed", "error"),
    [
        ([], "v0.4", "UnusedVariable", "PLCOPEN-CP17"),
        (["--docker", "img:tag"], "nightly", "PLCOPEN-CP17", "UnusedVariable"),
        (["--checker", "nightly"], "nightly", "PLCOPEN-CP17", "UnusedVariable"),
        (["--docker", "img:tag", "--checker", "v0.4"], "v0.4", "UnusedVariable", "PLCOPEN-CP17"),
    ],
    ids=["binary", "docker", "explicit", "docker-v0.4"],
)
def test_main_checker_scopes_allow_rules(
    sample_copy: Path, monkeypatch: pytest.MonkeyPatch, args: list[str], checker: str, allowed: str, error: str
) -> None:
    """Запись с ключом checker обосновывает находки и проверяется на использование только для своей версии."""
    found = (
        '[{"linenr":9,"column":10,"file":"","id":"UnusedVariable","msg":"variable: RVALUE"},'
        '{"linenr":9,"column":10,"file":"","id":"PLCOPEN-CP17","msg":"Input parameter \'RVALUE\'"}]'
    )
    fake_checker(monkeypatch, {"F_Clamp.st": found})
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    allow = sample_copy / "allow.toml"
    allow.write_text(ALLOW_BY_CHECKER, encoding="utf-8")
    assert R.main(["--root", str(sample_copy), "--allow", str(allow), *args]) == 1
    report = json.loads((sample_copy / "build" / "iec_checker.json").read_text(encoding="utf-8"))
    assert report["checker"] == checker
    assert {f["id"]: f["status"] for f in report["findings"]} == {allowed: "allowed", error: "error"}
    # запись другой версии не считается неиспользованной
    assert report["unused_allow"] == []
    assert f"для версии {checker}" in (sample_copy / "build" / "iec_checker.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("args", "found_id", "unused_id"),
    [([], "PLCOPEN-CP17", "UnusedVariable"), (["--checker", "nightly"], "UnusedVariable", "PLCOPEN-CP17")],
    ids=["v0.4", "nightly"],
)
def test_main_checker_scoped_rule_unused_for_own_version(
    sample_copy: Path, monkeypatch: pytest.MonkeyPatch, args: list[str], found_id: str, unused_id: str
) -> None:
    """Запись своей версии, под которую не попала ни одна находка, отчёт показывает неиспользованной."""
    found = f'[{{"linenr":9,"column":10,"file":"","id":"{found_id}","msg":"RVALUE"}}]'
    fake_checker(monkeypatch, {"F_Clamp.st": found})
    allow = sample_copy / "allow.toml"
    allow.write_text(ALLOW_BY_CHECKER, encoding="utf-8")
    assert R.main(["--root", str(sample_copy), "--allow", str(allow), *args]) == 1
    report = json.loads((sample_copy / "build" / "iec_checker.json").read_text(encoding="utf-8"))
    assert [f["status"] for f in report["findings"]] == ["error"]
    assert [r["id"] for r in report["unused_allow"]] == [unused_id]


def test_main_optional_and_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], make_tree: MakeTree
) -> None:
    def missing(*args: object, **kwargs: object) -> str:
        raise R.ToolMissing("нет iec_checker")

    monkeypatch.setattr(R, "find_binary", missing)
    assert R.main(["--optional"]) == 0
    assert "пропущен" in capsys.readouterr().out
    assert R.main([]) == 1
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert R.main(["--docker", "img"]) == 1
    monkeypatch.setattr(R, "find_binary", lambda *a, **k: "iec_checker")
    bad_allow = make_tree({"allow.toml": "[[allow]]\nid = 'X'\n"}) / "allow.toml"
    assert R.main(["--allow", str(bad_allow)]) == 2
    broken = make_tree({"src/POUs/FB_A/FB_A.decl.st": "FUNCTION_BLOCK FB_B\n", "src/POUs/FB_A/FB_A.impl.st": ";\n"})
    assert R.main(["--root", str(broken)]) == 1


@pytest.mark.integration
@requires_iec_checker
def test_integration_sample_parses_without_errors(sample_copy: Path) -> None:
    """Пониженный вариант примера разбирается настоящим iec_checker без ParserError/LexingError."""
    allow = sample_copy / "allow.toml"
    allow.write_text(ALLOW_SAMPLE, encoding="utf-8")
    code = R.main(["--root", str(sample_copy), "--tests", "--allow", str(allow)])
    report = json.loads((sample_copy / "build" / "iec_checker.json").read_text(encoding="utf-8"))
    parser_errors = [f for f in report["findings"] if f["id"] in R.PARSER_IDS or f["id"] == "ToolError"]
    assert parser_errors == []
    assert code == 0, [f for f in report["findings"] if f["status"] == "error"]
    assert report["summary"]["artifact"] > 0


@pytest.mark.integration
@requires_iec_checker
def test_integration_lowering_fixture_parses(tmp_path: Path) -> None:
    """Конструкции CODESYS вне грамматики iec_checker v0.4 (TIME(), a[i].x, ARRAY[0..GVL.N - 1], T#1h500ms,
    пустые операторы и тела, свойство Priority, ...) после понижения разбираются настоящим бинарником."""
    root = tmp_path / "lowering"
    shutil.copytree(LOWERING, root)
    allow = root / "allow.toml"
    allow.write_text(ALLOW_SAMPLE, encoding="utf-8")
    code = R.main(["--root", str(root), "--allow", str(allow)])
    report = json.loads((root / "build" / "iec_checker.json").read_text(encoding="utf-8"))
    broken = [f for f in report["findings"] if f["id"] in (*R.PARSER_IDS, "ToolError")]
    assert broken == []
    assert len(report["files"]) == 8
    # находки на строках исходников указывают на файлы раскладки
    assert all(f["source"] for f in report["findings"] if f["status"] != "artifact")
    assert code == 0, [f for f in report["findings"] if f["status"] == "error"]


@pytest.mark.integration
@requires_iec_checker
def test_integration_findings_point_to_source_lines(tmp_path: Path) -> None:
    """Находки настоящего iec_checker после понижения многострочных конструкций указывают на строки
    исходников: каждая строка примера sourcemap с «= 1.5 THEN» (в любом регистре) даёт PLCOPEN-CP8 ровно на своей строке
    (в теле ФБ, в методе и в аксессоре свойства, после a[i,\\n j], afb[i](...\\n), TIME(\\n), пустых
    ветвей и т. п.), а OutOfBounds поддиапазона в псевдониме типа относится к его DUT."""
    root = tmp_path / "sourcemap"
    shutil.copytree(SOURCEMAP, root)
    allow = root / "allow.toml"
    allow.write_text(ALLOW_SAMPLE, encoding="utf-8")
    R.main(["--root", str(root), "--allow", str(allow)])
    report = json.loads((root / "build" / "iec_checker.json").read_text(encoding="utf-8"))
    assert [f for f in report["findings"] if f["id"] in (*R.PARSER_IDS, "ToolError")] == []
    cp8 = {(f["source"], f["source_line"]) for f in report["findings"] if f["id"] == "PLCOPEN-CP8"}
    assert cp8 == sourcemap_lines(lambda line: SOURCEMAP_CP8 in line.upper())
    bounds = [f for f in report["findings"] if f["id"] == "OutOfBounds"]
    assert [(f["source"], "200" in f["msg"]) for f in bounds] == [("src/DUTs/T_Percent.dut.st", True)]
    # TIME() понижается вызовом заглушки, а не литералом длительности: ни ZeroDivision, ни PLCOPEN-CP28
    assert [f for f in report["findings"] if f["id"] in ("ZeroDivision", "PLCOPEN-CP28")] == []


@pytest.mark.integration
@requires_iec_checker
def test_integration_parser_error_fails(make_tree: MakeTree) -> None:
    root = make_tree(
        {
            "src/POUs/F_X/F_X.decl.st": "FUNCTION F_X : INT\nVAR_INPUT\n    iA : INT := 0;\nEND_VAR\n",
            # JMP и метки переходов понижение не обрабатывает
            "src/POUs/F_X/F_X.impl.st": "JMP lEnd;\nlEnd: F_X := iA;\n",
        }
    )
    assert R.main(["--root", str(root), "--allow", str(root / "none.toml")]) == 1
    report = json.loads((root / "build" / "iec_checker.json").read_text(encoding="utf-8"))
    assert report["findings"][0]["id"] == "ParserError"
    assert report["findings"][0]["source"] == "src/POUs/F_X/F_X.impl.st"


@pytest.mark.integration
@requires_iec_checker
@pytest.mark.parametrize("with_tests", [False, True], ids=["src", "src+tests"])
def test_integration_repository_sources(tmp_path: Path, with_tests: bool) -> None:
    """Исходники репозитория (src/, с флагом и tests/) проходят статанализ с его же файлом обоснований.

    Файл обоснований — tools/check/iec_checker_allow.toml репозитория (у проекта свой список), поэтому тест
    выполняется и в проектах: он проверяет их исходники их обоснованиями, а не исходники шаблона."""
    from conftest import REPO_ROOT

    if not (REPO_ROOT / "src" / "POUs").is_dir():
        pytest.skip("в src/ ещё нет POU")
    out = tmp_path / "out"
    reports = ["--json", str(tmp_path / "r.json"), "--md", str(tmp_path / "r.md")]
    args = ["--root", str(REPO_ROOT), "--out", str(out), *reports, *(["--tests"] if with_tests else [])]
    assert R.main(args) == 0
    if with_tests:
        # с tests/ используется каждое обоснование: устаревшие записи нужно удалить
        report = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
        assert report["unused_allow"] == []
