"""Тесты хост-части инструментов CODESYS (tools/codesys/cdshost/cli.py, cds_common.py) — без CODESYS.

Проверяются: строка запуска CODESYS, разрешение config.json и переменных окружения, файл задания,
шаги заданий, команда check, JUnit, отчёт TEST_REPORT.md, блокировки, защита проекта от перезаписи,
сравнение деревьев roundtrip, привязка сообщений компилятора к файлам, разбор процессов рантайма и
чистые функции cds_common (значения ПЛК, интервалы задач, GUID типов).

Настройки — эталон tools/tests/fixtures/config_template.json (conftest.template_config), а не
config.json репозитория: в проектах он свой, и тесты инструментов от него не зависят.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import cds_common as C
from cdshost import cli
from conftest import REPO_ROOT, MakeTree, template_config


def settings_for(root: Path, env: dict[str, str] | None = None, config: dict[str, Any] | None = None) -> cli.Settings:
    data = config if config is not None else template_config()
    environ = {"USERPROFILE": str(root / "home"), "HOME": str(root / "home")}
    environ.update(env or {})
    return cli.Settings(data, root, cli.make_getenv(environ, registry=False))


# ---------------------------------------------------------------------------
# Командная строка и задание
# ---------------------------------------------------------------------------


def test_cmdline_has_literal_quotes_after_equals() -> None:
    line = cli.build_cmdline(r"C:\P F\CODESYS.exe", "CODESYS V3.5 SP17 Patch 3", r"C:\r\tools\codesys\build.py")
    assert line == (
        r'"C:\P F\CODESYS.exe" --profile="CODESYS V3.5 SP17 Patch 3" --noUI '
        r'--runscript="C:\r\tools\codesys\build.py"'
    )


@pytest.mark.parametrize("bad", ['a"b', "a\nb", ""])
def test_cmdline_rejects_bad_values(bad: str) -> None:
    with pytest.raises(cli.CdsError) as err:
        cli.build_cmdline("CODESYS.exe", bad, "x.py")
    assert err.value.code == cli.EXIT_USAGE


def test_write_job_is_utf8_lf(tmp_path: Path) -> None:
    path = tmp_path / "a" / "job.json"
    cli.write_job(path, {"steps": [{"action": "import", "name": "проект"}]})
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    assert json.loads(raw.decode("utf-8"))["steps"][0]["name"] == "проект"


# ---------------------------------------------------------------------------
# Настройки: config.json + окружение
# ---------------------------------------------------------------------------


def test_template_config_defaults() -> None:
    """Значения по умолчанию эталона (config.json шаблона); живой config.json — test_cds_config.py."""
    data = template_config()
    assert data["device"]["type"]["default"] == 4096
    assert data["device"]["id"]["default"] == "0000 0001"
    assert data["modes"]["normal"]["tasks"][0] == {"name": "MainTask", "interval_ms": 20, "pous": ["PRG_Main"]}
    assert data["modes"]["test"]["tasks"][0] == {"name": "TestTask", "interval_ms": 10, "pous": ["PRG_Tests"]}
    assert data["modes"]["test"]["libraries"] == ["counit"]
    # Standard — плейсхолдер #Standard, как в проектах IDE: версию задаёт профиль, доступны TON и Standard.TON
    assert data["libraries"]["standard"]["placeholder"] == "Standard"
    assert data["libraries"]["standard"]["version"] == "*"
    # явные namespace и qualified_only: импорт возвращает их, если ссылку поменяли в IDE, а свой ключ
    # проекта с другим пространством имён — отказ, а не тихая подмена (код опирается на Standard.TON)
    assert data["libraries"]["standard"]["namespace"] == "Standard"
    assert data["libraries"]["standard"]["qualified_only"] is False
    assert data["library"]["libraries"] == ["standard"]


def test_defaults_resolve_relative_to_repo(tmp_path: Path) -> None:
    root = tmp_path / "my-plc"
    s = settings_for(root)
    assert s.value("project.name") == "my-plc"
    assert s.project_path(False) == root / "build" / "my-plc.project"
    assert s.project_path(True) == root / "build" / "my-plc-tests.project"
    assert s.profile == "CODESYS V3.5 SP17 Patch 3"
    assert s.path("runtime.credentials") == root / "home" / ".local" / "plc-tools" / "cds-runtime" / "credentials.json"
    assert s.path("runtime.boot_cfg") == root / "home" / ".local" / "plc-tools" / "cds-runtime" / "boot.cfg"
    assert s.device() == {"name": "Device", "type": 4096, "id": "0000 0001", "version": "3.5.17.30"}


def test_env_overrides(tmp_path: Path) -> None:
    creds = tmp_path / "c.json"
    s = settings_for(
        tmp_path,
        {
            "CDS_PROJECT_NAME": "demo",
            "CODESYS_PROFILE": "Other Profile",
            "CODESYS_RUNTIME_CREDENTIALS": str(creds),
            "CDS_DEVICE_ID": "0000 0004",
            "CDS_TEST_TIMEOUT_S": "30",
            "CODESYS_RUNTIME_DIR": str(tmp_path / "rt"),
        },
    )
    assert s.project_path(False) == tmp_path / "build" / "demo.project"
    assert s.profile == "Other Profile"
    assert s.path("runtime.credentials") == creds
    assert s.device()["id"] == "0000 0004"
    assert s.number("tests.timeout_s") == 30.0
    assert s.path("runtime.pid_file") == tmp_path / "rt" / "runtime.pid.json"


def test_exe_candidates_pick_first_existing(tmp_path: Path) -> None:
    pf86 = tmp_path / "pf86"
    pf = tmp_path / "pf"
    exe = pf / "CODESYS 3.5.17.30" / "CODESYS" / "Common" / "CODESYS.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    s = settings_for(tmp_path, {"ProgramFiles(x86)": str(pf86), "ProgramFiles": str(pf)})
    assert s.codesys_exe == exe
    env_exe = tmp_path / "x" / "CODESYS.exe"
    env_exe.parent.mkdir()
    env_exe.write_text("")
    s2 = settings_for(tmp_path, {"CODESYS_EXE": str(env_exe)})
    assert s2.codesys_exe == env_exe


def test_missing_exe_is_environment_error(tmp_path: Path) -> None:
    s = settings_for(tmp_path, {"ProgramFiles(x86)": str(tmp_path / "a"), "ProgramFiles": str(tmp_path / "b")})
    with pytest.raises(cli.CdsError) as err:
        _ = s.codesys_exe
    assert err.value.code == cli.EXIT_ENV
    assert "CODESYS.exe" in str(err.value)


def test_unset_variable_in_default_is_reported(tmp_path: Path) -> None:
    s = settings_for(tmp_path)
    with pytest.raises(cli.CdsError) as err:
        s.path("lock.path")
    assert "LOCALAPPDATA" in str(err.value)
    s2 = settings_for(tmp_path, {"LOCALAPPDATA": str(tmp_path / "lad")})
    assert s2.path("lock.path") == tmp_path / "lad" / "plc-tools" / "codesys-runtime.lock"


def test_getenv_prefers_process_env() -> None:
    getenv = cli.make_getenv({"A": "1", "EMPTY": ""}, registry=False)
    assert getenv("A") == "1"
    assert getenv("EMPTY") is None
    assert getenv("NOPE") is None


def test_mode_config_resolves_libraries(tmp_path: Path) -> None:
    lib = tmp_path / "counit.library"
    s = settings_for(tmp_path, {"COUNIT_LIBRARY": str(lib)})
    mode = s.mode_config("test")
    assert mode["tasks"][0]["name"] == "TestTask"
    spec = mode["libraries"][0]
    assert spec["namespace"] == "coUnit"
    assert spec["version"] == "1.2.0.0"
    assert spec["install_from"] == str(lib)
    assert spec["install_env"] == "COUNIT_LIBRARY"
    # Standard (library.libraries) — во всех режимах, coUnit — только в test
    assert [x["key"] for x in mode["libraries"]] == ["counit", "standard"]
    normal = s.mode_config("normal")["libraries"]
    assert [x["key"] for x in normal] == ["standard"]
    assert normal[0]["placeholder"] == "Standard" and normal[0]["install_from"] is None
    assert [x["namespace"] for x in s.other_libraries("normal")] == ["coUnit"]
    assert s.other_libraries("test") == []
    assert settings_for(tmp_path).mode_config("test")["libraries"][0]["install_from"] is None


def test_mode_libraries_without_standard(tmp_path: Path) -> None:
    """Проект, который убрал Standard из library.libraries, получает только библиотеки режима."""
    data = template_config()
    data["library"]["libraries"] = []
    s = settings_for(tmp_path, config=data)
    assert s.mode_config("normal")["libraries"] == []
    assert [x["key"] for x in s.mode_config("test")["libraries"]] == ["counit"]


def test_same_key_in_mode_and_library_is_one_reference(tmp_path: Path) -> None:
    """Standard и в modes.normal.libraries (так его подключали проекты раньше), и в library.libraries — один ключ."""
    data = template_config()
    data["modes"]["normal"]["libraries"] = ["standard"]
    s = settings_for(tmp_path, config=data)
    assert [x["key"] for x in s.mode_config("normal")["libraries"]] == ["standard"]
    assert s.referenced_library_keys() == ["standard", "counit"]


def test_unknown_mode_is_usage_error(tmp_path: Path) -> None:
    with pytest.raises(cli.CdsError) as err:
        settings_for(tmp_path).mode_config("nope")
    assert err.value.code == cli.EXIT_USAGE


def test_load_config_errors(tmp_path: Path) -> None:
    with pytest.raises(cli.CdsError):
        cli.load_config(tmp_path / "none.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(cli.CdsError) as err:
        cli.load_config(bad)
    assert err.value.code == cli.EXIT_USAGE


# ---------------------------------------------------------------------------
# Шаги заданий
# ---------------------------------------------------------------------------


def test_job_steps(tmp_path: Path) -> None:
    s = settings_for(tmp_path)
    project = s.project_path(True)
    imp = cli.import_step(s, True, project, clean=True)
    assert imp["action"] == "import" and imp["mode"] == "test" and imp["with_tests"] is True
    assert imp["clean"] is True and imp["tests_folder"] == "Tests"
    assert imp["log"] == str(tmp_path / "build" / "import.log")
    assert imp["device"]["type"] == 4096
    test = cli.test_step(s, project)
    assert test["runtime"] == {
        "gateway_name": "Gateway-1",
        "gateway_host": "localhost",
        "gateway_port": 1217,
        "device_address": "127.0.0.1",
        "device_port": 11740,
    }
    assert test["tests"]["runner"] == "coUnit.GVL_coUnit.coUnitRunner"
    assert test["results"] == str(tmp_path / "build" / "test-results.json")
    assert test["meta"]["runtime"] == "CODESYS Control Win V3 (пользовательский процесс)"
    exp = cli.export_step(s, project, tmp_path / "out", True)
    assert exp["out_root"] == str(tmp_path / "out") and exp["with_tests"] is True


def test_check_step(tmp_path: Path) -> None:
    root = tmp_path / "pump-station"
    s = settings_for(root)
    step = cli.check_step(s, False)
    assert step["action"] == "check" and step["mode"] == "normal" and step["with_tests"] is False
    assert step["project"] == str(root / "build" / "codesys" / "pump-station-check.project")
    assert [x["key"] for x in step["libraries"]] == ["standard"]
    assert step["repository"] == "System" and step["tests_folder"] == "Tests"
    # устройство — чтобы скопировать в пул проверки ссылки, которые оно добавляет приложению само
    assert step["device"] == {"name": "Device", "type": 4096, "id": "0000 0001", "version": "3.5.17.30"}
    assert step["log"] == str(root / "build" / "check.log") and step["report"] == str(root / "build" / "check.json")
    tests = cli.check_step(s, True)
    assert tests["mode"] == "test" and tests["with_tests"] is True
    assert [x["key"] for x in tests["libraries"]] == ["counit", "standard"]


def check_result(errors: int, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    step: dict[str, Any] = {
        "action": "check",
        "ok": errors == 0,
        "objects": 7,
        "errors": errors,
        "warnings": 0,
        "messages": messages or [],
        "duration_s": 1.0,
    }
    if errors:
        step["error"] = f"проверка всех объектов: ошибок {errors}"
    return {"ok": errors == 0, "exit_code": 1 if errors else 0, "steps": [step]}


def test_cmd_check_reports_unreachable_errors_with_source(
    make_tree: MakeTree, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_tree(LAYOUT)
    s = settings_for(root, {"LOCALAPPDATA": str(root / "lad")})
    (root / "build").mkdir()
    (root / "build" / "check.json").write_text(json.dumps({"messages": []}), encoding="utf-8")
    msg = {
        "severity": "Error",
        "code": "C0032",
        "object": "FB_A.Run",
        "text": "Невозможно конвертировать тип 'DINT' в тип 'INT'",
        "position": "Строка 1, Столбец 1 (Реализ.)",
    }
    jobs: list[dict[str, Any]] = []

    def fake_run(settings: cli.Settings, script: str, job: dict[str, Any], label: str, **kw: Any) -> dict[str, Any]:
        jobs.append({"script": script, "job": job, "label": label})
        return check_result(1, [msg])

    monkeypatch.setattr(cli, "run_codesys", fake_run)
    assert cli.cmd_check(s, cli.build_parser().parse_args(["check", "--tests"])) == cli.EXIT_FAILED
    assert jobs[0]["script"] == "check_sources.py" and jobs[0]["label"] == "check"
    step = jobs[0]["job"]["steps"][0]
    assert step["action"] == "check" and step["with_tests"] is True
    out = capsys.readouterr().out
    assert "src/POUs/FB_A/Run.method.impl.st:1: Error C0032" in out
    saved = json.loads((root / "build" / "check.json").read_text(encoding="utf-8"))
    assert saved["messages"][0]["source"] == "src/POUs/FB_A/Run.method.impl.st:1"
    assert not (root / "build" / "codesys" / "cds.lock.owner").exists()  # блокировка снята
    monkeypatch.setattr(cli, "run_codesys", lambda *a, **k: check_result(0))
    assert cli.cmd_check(s, cli.build_parser().parse_args(["check"])) == cli.EXIT_OK
    assert "все объекты src/ скомпилированы без ошибок (7 объектов)" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# JUnit и отчёт
# ---------------------------------------------------------------------------


def sample_results(failed: bool = True, finished: bool = True) -> dict[str, Any]:
    cases = [
        {"name": "Passes", "class_name": "Device.Application.PRG_Tests.fbA", "status": "PASS"},
        {"name": "Skipped", "class_name": "Device.Application.PRG_Tests.fbA", "status": "SKIP"},
    ]
    if failed:
        cases.append(
            {
                "name": "Fails",
                "class_name": "Device.Application.PRG_Tests.fbA",
                "status": "FAIL",
                "message": "expected <3> | got 4",
                "failure_type": "E_AssertionType.Type_INT",
            }
        )
    n_failed = 1 if failed else 0
    return {
        "started": "2026-10-16T00:02:49",
        "finished": finished,
        "codesys_version": "3.5.17.30",
        "profile": "CODESYS V3.5 SP17 Patch 3",
        "runtime": "CODESYS Control Win V3 (пользовательский процесс)",
        "device": "CODESYS Control Win V3 (4096 / 0000 0001 / 3.5.17.30)",
        "framework": "coUnit (CfUnit) 1.2.0.0",
        "commit": "abc1234",
        "build": {"errors": 0, "warnings": 0},
        "totals": {"suites": 1, "tests": len(cases), "passed": 1, "failed": n_failed, "skipped": 1},
        "suites": [
            {
                "name": "PRG_Tests.fbA",
                "tests": len(cases),
                "failed": n_failed,
                "skipped": 1,
                "cases": cases,
            }
        ],
    }


def test_junit_structure() -> None:
    root = ET.fromstring(cli.results_to_junit(sample_results()))
    assert root.tag == "testsuites"
    assert root.attrib["tests"] == "3" and root.attrib["failures"] == "1" and root.attrib["skipped"] == "1"
    suite = root.find("testsuite")
    assert suite is not None and suite.attrib["name"] == "PRG_Tests.fbA"
    cases = {c.attrib["name"]: c for c in suite.findall("testcase")}
    failure = cases["Fails"].find("failure")
    assert failure is not None
    assert failure.attrib["message"] == "expected <3> | got 4"
    assert failure.attrib["type"] == "E_AssertionType.Type_INT"
    assert cases["Skipped"].find("skipped") is not None
    assert cases["Passes"].find("failure") is None
    assert cases["Passes"].attrib["classname"] == "Device.Application.PRG_Tests.fbA"


def test_junit_unfinished_run_is_error() -> None:
    results = sample_results(failed=False, finished=False)
    results["error"] = "таймаут"
    root = ET.fromstring(cli.results_to_junit(results))
    assert root.attrib["errors"] == "1"
    errors = root.findall("./testsuite/testcase/error")
    assert errors and errors[0].attrib["message"] == "таймаут"


def test_report_section_content() -> None:
    section = cli.render_report(sample_results())
    assert section.startswith(cli.REPORT_BEGIN) and section.rstrip().endswith(cli.REPORT_END)
    assert "Проверено в CODESYS 3.5.17.30 / CODESYS Control Win V3 (пользовательский процесс)" in section
    assert "есть ошибки" in section
    assert "| `PRG_Tests.fbA` | `Fails` | expected <3> \\| got 4 | E_AssertionType.Type_INT |" in section
    assert "abc1234" in section
    green = cli.render_report(sample_results(failed=False))
    assert "все тесты пройдены" in green and "_Нет._" in green


def test_update_report_inserts_then_replaces() -> None:
    doc = "# Отчёт\n\nВступление.\n\n## Окружение\n\nтекст\n"
    first = cli.update_report(doc, cli.render_report(sample_results()))
    assert first.index(cli.REPORT_BEGIN) < first.index("## Окружение")
    assert first.startswith("# Отчёт\n\nВступление.\n\n")
    second = cli.update_report(first, cli.render_report(sample_results(failed=False)))
    assert second.count(cli.REPORT_BEGIN) == 1 and second.count(cli.REPORT_END) == 1
    assert "все тесты пройдены" in second and "есть ошибки" not in second
    assert second.endswith("## Окружение\n\nтекст\n")
    assert cli.update_report(second, cli.render_report(sample_results(failed=False))) == second


def test_report_command_writes_doc(tmp_path: Path) -> None:
    results = tmp_path / "r.json"
    results.write_text(json.dumps(sample_results()), encoding="utf-8")
    doc = tmp_path / "TEST_REPORT.md"
    doc.write_text("# Отчёт о тестировании\n\n## Тесты\n", encoding="utf-8")
    s = settings_for(tmp_path)
    args = cli.build_parser().parse_args(["report", "--results", str(results), "--doc", str(doc)])
    assert cli.cmd_report(s, args) == cli.EXIT_OK
    assert cli.REPORT_BEGIN in doc.read_text(encoding="utf-8")
    out = tmp_path / "j.xml"
    args = cli.build_parser().parse_args(["junit", "--results", str(results), "--out", str(out)])
    assert cli.cmd_junit(s, args) == cli.EXIT_OK
    assert ET.parse(out).getroot().attrib["failures"] == "1"


# ---------------------------------------------------------------------------
# Блокировки и состояние проекта
# ---------------------------------------------------------------------------


def test_file_lock_excludes_second_holder(tmp_path: Path) -> None:
    path = tmp_path / "locks" / "rt.lock"
    first = cli.FileLock(path, timeout_s=5, purpose="first")
    with first:
        assert "first" in first.owner()
        second = cli.FileLock(path, timeout_s=0.3, poll_s=0.05, purpose="second")
        with pytest.raises(cli.CdsError) as err:
            second.acquire()
        assert err.value.code == cli.EXIT_LOCK
        assert "first" in str(err.value)
    with cli.FileLock(path, timeout_s=1, purpose="third") as third:
        assert "third" in third.owner()
    assert not third.owner_path.exists()


def test_project_guard(tmp_path: Path) -> None:
    s = settings_for(tmp_path)
    project = tmp_path / "build" / "p.project"
    project.parent.mkdir(parents=True)
    cli.check_project_state(s, project, force=False)  # нет проекта — можно
    project.write_bytes(b"v1")
    cli.check_project_state(s, project, force=False)  # нет записи — можно
    cli.record_project_state(s, project, ("src",))
    cli.check_project_state(s, project, force=False)
    project.write_bytes(b"v2 - saved in IDE")
    with pytest.raises(cli.CdsError) as err:
        cli.check_project_state(s, project, force=False)
    assert "export" in str(err.value)
    cli.check_project_state(s, project, force=True)


def test_sources_guard_before_export(tmp_path: Path) -> None:
    s = settings_for(tmp_path)
    project = tmp_path / "build" / "p.project"
    project.parent.mkdir(parents=True)
    project.write_bytes(b"v1")
    decl = tmp_path / "src" / "POUs" / "P" / "P.decl.st"
    decl.parent.mkdir(parents=True)
    decl.write_bytes(b"PROGRAM P\n")
    cli.check_sources_state(s, project, ("src",), force=False)  # нет записи — можно
    cli.record_project_state(s, project, ("src",))
    cli.check_sources_state(s, project, ("src",), force=False)
    (tmp_path / "src" / "POUs" / "P" / "P.impl.st").write_bytes(b"// added after import\n")
    with pytest.raises(cli.CdsError) as err:
        cli.check_sources_state(s, project, ("src",), force=False)
    assert "--force" in str(err.value)
    cli.check_sources_state(s, project, ("src",), force=True)
    # tests/ не входит в отпечаток экспорта без --tests
    cli.record_project_state(s, project, ("src",))
    (tmp_path / "tests" / "POUs").mkdir(parents=True)
    (tmp_path / "tests" / "POUs" / "x.st").write_bytes(b"x")
    cli.check_sources_state(s, project, ("src",), force=False)


def test_sources_digest_depends_on_paths_and_content(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.st").write_bytes(b"x")
    first = cli.sources_digest(tmp_path, ("src",))
    (tmp_path / "src" / "a.st").rename(tmp_path / "src" / "b.st")
    second = cli.sources_digest(tmp_path, ("src",))
    (tmp_path / "src" / "b.st").write_bytes(b"y")
    third = cli.sources_digest(tmp_path, ("src",))
    assert len({first, second, third}) == 3
    assert cli.sources_digest(tmp_path, ("src", "tests")) == third


# ---------------------------------------------------------------------------
# roundtrip: сравнение деревьев
# ---------------------------------------------------------------------------


def test_compare_trees(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    for root in (a, b):
        (root / "src" / "POUs" / "P").mkdir(parents=True)
        (root / "src" / "POUs" / "P" / "P.decl.st").write_bytes(b"PROGRAM P\n")
        (root / "src" / "README.md").write_bytes(b"ignored")
    assert cli.compare_trees(a, b, ("src", "tests")) == []
    (b / "src" / "POUs" / "P" / "P.decl.st").write_bytes(b"PROGRAM P\nVAR\nEND_VAR\n")
    (a / "src" / "POUs" / "P" / "P.impl.st").write_bytes(b"x();\n")
    (b / "src" / "POUs" / "P" / "Extra.method.decl.st").write_bytes(b"METHOD Extra\n")
    report = cli.compare_trees(a, b, ("src", "tests"))
    assert "только в исходниках: src/POUs/P/P.impl.st" in report
    assert "только в экспорте: src/POUs/P/Extra.method.decl.st" in report
    assert "различается: src/POUs/P/P.decl.st" in report
    assert any(line.strip() == "+VAR" for line in report)


# ---------------------------------------------------------------------------
# Сообщения компилятора -> файл:строка
# ---------------------------------------------------------------------------


LAYOUT = {
    "src/POUs/FB_A/FB_A.decl.st": "FUNCTION_BLOCK FB_A\nVAR\n    x : INT;\nEND_VAR\n",
    "src/POUs/FB_A/FB_A.impl.st": "x := 1;\n",
    "src/POUs/FB_A/Run.method.decl.st": "METHOD Run\n",
    "src/POUs/FB_A/Run.method.impl.st": "x := 2;\n",
    "src/POUs/FB_A/Count.prop.decl.st": "PROPERTY Count : INT\n",
    "src/POUs/FB_A/Count.get.impl.st": "Count := x;\n",
    "src/DUTs/Motor/ST_M.dut.st": "TYPE ST_M :\nSTRUCT\n    a : INT;\nEND_STRUCT\nEND_TYPE\n",
    "tests/POUs/FB_A_Test/FB_A_Test.decl.st": "FUNCTION_BLOCK FB_A_Test\n",
    "tests/POUs/FB_A_Test/FB_A_Test.impl.st": "// тело\n",
}


@pytest.mark.parametrize(
    ("obj", "position", "expected"),
    [
        ("FB_A", "Строка 3 (Объявл.)", "src/POUs/FB_A/FB_A.decl.st:3"),
        ("FB_A", "Строка 1, Столбец 1 (Реализ.)", "src/POUs/FB_A/FB_A.impl.st:1"),
        ("FB_A.Run", "Строка 1, Столбец 5 (Реализ.)", "src/POUs/FB_A/Run.method.impl.st:1"),
        ("FB_A.Run", "Line 1 (Decl)", "src/POUs/FB_A/Run.method.decl.st:1"),
        ("FB_A.Count.Get", "Строка 1, Столбец 1 (Реализ.)", "src/POUs/FB_A/Count.get.impl.st:1"),
        ("FB_A.Count.Get", "Строка 1 (Объявл.)", None),  # объявление по умолчанию — файла нет
        ("FB_A.Count", "Строка 1 (Объявл.)", "src/POUs/FB_A/Count.prop.decl.st:1"),
        ("Motor.ST_M", "Строка 4 (Объявл.)", "src/DUTs/Motor/ST_M.dut.st:4"),
        ("Tests.FB_A_Test", "Строка 1, Столбец 1 (Реализ.)", "tests/POUs/FB_A_Test/FB_A_Test.impl.st:1"),
        ("Unit Test Framework for CODESYS.GVLs.GVL_coUnit", "Строка 33", None),
        (None, None, None),
    ],
)
def test_source_location(make_tree: MakeTree, obj: str | None, position: str | None, expected: str | None) -> None:
    root = make_tree(LAYOUT)
    objects = cli.layout_objects(root)
    assert cli.source_location(obj, position, objects) == expected


# ---------------------------------------------------------------------------
# Рантайм: процессы, каталог
# ---------------------------------------------------------------------------


def test_parse_processes_and_ownership(tmp_path: Path) -> None:
    boot = Path(r"C:\Users\u\.local\plc-tools\cds-runtime\boot.cfg")
    single = json.dumps(
        {
            "ProcessId": 10,
            "CommandLine": r'"C:\P\CODESYSControlService.exe" -d "C:\Users\u\.local\plc-tools\cds-runtime\boot.cfg"',
            "ExecutablePath": r"C:\P\CODESYSControlService.exe",
            "Created": "2026-10-15T23:33:59.8459040+03:00",
        }
    )
    procs = cli.parse_processes(single)
    assert procs[0]["pid"] == 10
    assert cli.is_our_runtime(procs[0], boot)
    service = cli.parse_processes(json.dumps([{"ProcessId": 11, "CommandLine": r'"C:\P\CODESYSControlService.exe"'}]))
    assert not cli.is_our_runtime(service[0], boot)
    assert cli.parse_processes("  ") == []


def test_runtime_init_creates_files(tmp_path: Path) -> None:
    template = tmp_path / "pd" / "CODESYS" / "CODESYSControlWinV3" / "ABC" / "CODESYSControl.cfg"
    template.parent.mkdir(parents=True)
    template.write_text("[CmpUserMgr]\n", encoding="utf-8")
    rt = tmp_path / "rt"
    s = settings_for(tmp_path, {"CODESYS_RUNTIME_DIR": str(rt), "ProgramData": str(tmp_path / "pd")})
    done = cli.runtime_init(s)
    assert len(done) == 3
    boot = (rt / "boot.cfg").read_bytes()
    assert boot.startswith(b"[SysFile]\r\nWindows.WorkingDirectory=") and boot.endswith(b"\\\r\n")
    assert (rt / "work" / "CODESYSControl.cfg").read_text(encoding="utf-8") == "[CmpUserMgr]\n"
    creds = json.loads((rt / "credentials.json").read_text(encoding="utf-8"))
    assert creds["user"] == "cdsci" and len(creds["password"]) >= 20
    for line in done:
        assert creds["password"] not in line
    assert cli.runtime_init(s) == []  # повторно ничего не меняет


def test_age_minutes() -> None:
    assert cli._age_min(None) is None
    assert cli._age_min("not a date") is None
    age = cli._age_min("2020-01-01T00:00:00+00:00")
    assert age is not None and age > 60


# ---------------------------------------------------------------------------
# cds_common: чистые функции (общие с IronPython)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "value"),
    [
        ("TRUE", True),
        ("FALSE", False),
        ("UINT#7", 7),
        ("INT#-3", -3),
        ("16#FF", 255),
        ("DWORD#16#1_0", 16),
        ("REAL#1.5", 1.5),
        ("2.25", 2.25),
        ("42", 42),
        ("'Device.Application.PRG_Tests.fbA'", "Device.Application.PRG_Tests.fbA"),
        ("'it$'s $$5$N'", "it's $5\n"),
        ("'$41$42'", "AB"),
        ('"$0416"', "Ж"),
        ("''", ""),
        ("E_AssertionType.Type_REAL", "E_AssertionType.Type_REAL"),
        ("TIME#1s", "TIME#1s"),
    ],
)
def test_plc_value(raw: str, value: object) -> None:
    assert C.plc_value(raw) == value


def test_plc_value_none() -> None:
    assert C.plc_value(None) is None


@pytest.mark.parametrize(
    ("raw", "unit", "ms"),
    [
        ("t#20ms", None, 20.0),
        ("T#1s", None, 1000.0),
        ("T#1s500ms", None, 1500.0),
        ("20", "ms", 20.0),
        ("2", "s", 2000.0),
    ],
)
def test_interval_ms(raw: str, unit: str | None, ms: float) -> None:
    assert C.interval_ms(raw, unit) == ms


def test_kind_of_type_and_accessor_default() -> None:
    assert C.kind_of_type("{6F9DAC99-8DE1-4EFC-8465-68AC443B7D08}") == C.K_POU
    assert C.kind_of_type("f89f7675-27f1-46b3-8abb-b7da8e774ffd") == C.K_METHOD
    assert C.kind_of_type("28747452-a93d-4b34-8d05-d2c6018edd7d") == C.K_ACCESSOR
    assert C.kind_of_type("00000000-0000-0000-0000-000000000000") == C.K_OTHER
    assert C.is_default_accessor_decl("VAR\nEND_VAR\n")
    assert C.is_default_accessor_decl("VAR END_VAR")
    assert not C.is_default_accessor_decl("VAR\n    i : INT;\nEND_VAR\n")


def test_log_collects_warnings(tmp_path: Path) -> None:
    log = C.Log(str(tmp_path / "l" / "x.log"))
    log.info("начало")
    log.warn("осторожно")
    log.error("ошибка")
    log.close()
    text = (tmp_path / "l" / "x.log").read_text(encoding="utf-8")
    assert "WARN  осторожно" in text and "ERROR ошибка" in text
    assert log.warnings == ["осторожно"] and log.errors == ["ошибка"]


def test_write_json_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "r.json"
    C.write_json(str(path), {"b": 1, "a": "я"})
    assert path.read_bytes() == '{\n  "a": "я",\n  "b": 1\n}\n'.encode()


def test_precompile_cache_paths() -> None:
    paths = C.precompile_cache_paths(os.path.join("b", "plcrev.project"))
    assert [os.path.basename(p) for p in paths] == ["plcrev_project.precompilecache"]
    dotted = [os.path.basename(p) for p in C.precompile_cache_paths("a.b.project")]
    assert dotted == ["a.b_project.precompilecache", "a_b_project.precompilecache"]


def test_remove_precompile_cache(tmp_path: Path) -> None:
    project = tmp_path / "p.project"
    project.write_bytes(b"project")
    cache = tmp_path / "p_project.precompilecache"
    cache.write_bytes(b"cache")
    other = tmp_path / "p-tests_project.precompilecache"
    other.write_bytes(b"other project cache")
    log = C.Log(str(tmp_path / "log.txt"))
    assert C.remove_precompile_cache(str(project), log) == [str(cache)]
    log.close()
    assert not cache.exists() and other.exists() and project.exists()
    assert "кэш предкомпиляции" in (tmp_path / "log.txt").read_text(encoding="utf-8")
    assert C.remove_precompile_cache(str(project)) == []


def write_lock(project: Path, text: str) -> Path:
    lock = Path(C.project_lock_path(str(project)))
    lock.write_bytes(text.encode("utf-8"))
    return lock


def test_read_project_lock(tmp_path: Path) -> None:
    project = tmp_path / "p.project"
    assert C.read_project_lock(str(project)) is None
    write_lock(project, "hello\r\nDESKTOP-1\r\n13092\r\n639276982453105053\r\n")
    info = C.read_project_lock(str(project))
    assert info is not None
    assert (info["user"], info["host"], info["pid"]) == ("hello", "DESKTOP-1", 13092)
    write_lock(project, "")
    empty = C.read_project_lock(str(project))
    assert empty is not None and empty["pid"] is None and empty["host"] == ""


@pytest.mark.parametrize(
    ("host", "running", "stale"),
    [
        ("DESKTOP-1", None, True),  # процесса нет — CODESYS был остановлен (таймаут, сбой)
        ("desktop-1", "CODESYS", False),  # проект открыт в IDE
        ("DESKTOP-1", "notepad", True),  # PID переиспользован другим процессом
        ("OTHER-PC", None, False),  # другой компьютер — проверить нельзя
        ("", None, False),
    ],
)
def test_lock_is_stale(host: str, running: str | None, stale: bool) -> None:
    info = {"path": "p.project.~u", "user": "u", "host": "DESKTOP-1", "pid": 42}
    assert C.lock_is_stale(info, host, lambda pid: running) is stale
    assert C.lock_is_stale(dict(info, pid=None), host, lambda pid: None) is False


def test_check_project_lock(tmp_path: Path) -> None:
    project = tmp_path / "p.project"
    project.write_bytes(b"project")
    C.check_project_lock(str(project), host="PC")  # блокировки нет
    lock = write_lock(project, "u\r\nPC\r\n42\r\n1\r\n")
    with pytest.raises(C.StepError) as err:
        C.check_project_lock(str(project), host="PC", name_of_pid=lambda pid: "CODESYS")
    assert err.value.code == C.EXIT_INTERNAL and "PID 42" in str(err.value) and lock.exists()
    log = C.Log(str(tmp_path / "log.txt"))
    C.check_project_lock(str(project), log, host="PC", name_of_pid=lambda pid: None)
    log.close()
    assert not lock.exists() and project.exists()
    assert "устаревший файл блокировки" in log.warnings[0]


@pytest.mark.parametrize(("code", "expected"), [(None, C.EXIT_FAILED), (C.EXIT_INTERNAL, C.EXIT_INTERNAL)])
def test_run_main_uses_step_error_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int | None, expected: int
) -> None:
    name = f"fake_step_{expected}"  # своё имя модуля на каждый вариант: __import__ кэширует модули
    module = tmp_path / f"{name}.py"
    args = "" if code is None else f", code={code}"
    module.write_text(
        f"import cds_common as C\n\ndef run(ctx, step):\n    raise C.StepError('рантайм недоступен'{args})\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(C.ACTION_MODULES, "fake", name)
    monkeypatch.delitem(sys.modules, name, raising=False)
    result = tmp_path / "result.json"
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"result": str(result), "steps": [{"action": "fake"}]}), encoding="utf-8")
    monkeypatch.setenv(C.JOB_ENV, str(job))
    with pytest.raises(SystemExit) as stop:
        C.run_main("fake")
    assert stop.value.code == expected
    data = json.loads(result.read_text(encoding="utf-8"))
    assert data["ok"] is False and data["exit_code"] == expected
    assert data["steps"][0]["error"] == "рантайм недоступен" and "internal" not in data["steps"][0]


def test_cmd_test_removes_stale_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Сборка упала — junit.xml и test-results.json прошлого зелёного прогона не остаются в build/."""
    s = settings_for(tmp_path, {"LOCALAPPDATA": str(tmp_path / "lad")})
    build = tmp_path / "build"
    build.mkdir()
    (build / "junit.xml").write_text("<testsuites failures='0'/>", encoding="utf-8")
    (build / "test-results.json").write_text("{}", encoding="utf-8")
    failed_build = {
        "ok": False,
        "exit_code": 1,
        "steps": [
            {"action": "import", "ok": True},
            {"action": "build", "ok": False, "errors": 1, "warnings": 0, "messages": []},
        ],
    }
    monkeypatch.setattr(cli, "ensure_runtime", lambda *a, **k: {"running": True})
    monkeypatch.setattr(cli, "run_codesys", lambda *a, **k: failed_build)
    args = cli.build_parser().parse_args(["test"])
    assert cli.cmd_test(s, args) == cli.EXIT_FAILED
    assert not (build / "junit.xml").exists() and not (build / "test-results.json").exists()


def test_print_steps_without_test_totals(capsys: pytest.CaptureFixture[str]) -> None:
    cli._print_steps({"steps": [{"action": "test", "ok": False, "error": "не удалось войти", "duration_s": 1.0}]})
    out = capsys.readouterr().out
    assert "тесты не выполнялись" in out and "None" not in out


@pytest.mark.parametrize(
    ("decl", "expected"),
    [
        (
            "VAR_GLOBAL PERSISTENT RETAIN\n    x : INT;\nEND_VAR\n",
            "VAR_GLOBAL            RETAIN\n    x : INT;\nEND_VAR\n",
        ),
        ("// шапка\nvar_global retain persistent\nEND_VAR\n", "// шапка\nvar_global retain           \nEND_VAR\n"),
        (  # комментарий и имя переменной со словом PERSISTENT не трогаются
            "VAR_GLOBAL (* PERSISTENT *) PERSISTENT\n    PERSISTENT_x : INT; // PERSISTENT\nEND_VAR\n",
            "VAR_GLOBAL (* PERSISTENT *)           \n    PERSISTENT_x : INT; // PERSISTENT\nEND_VAR\n",
        ),
        ("VAR_GLOBAL\n    x : INT;\nEND_VAR\n", "VAR_GLOBAL\n    x : INT;\nEND_VAR\n"),
    ],
)
def test_pvl_as_gvl_keeps_positions(decl: str, expected: str) -> None:
    """Заменитель Persistent Variables в cds.py check: без PERSISTENT, строки и столбцы — как в файле."""
    steps: Any = importlib.import_module("check_sources")  # скрипт CODESYS, без CODESYS импортируется
    assert steps.pvl_as_gvl(decl) == expected


def test_check_option_files(tmp_path: Path) -> None:
    """Файлы настроек пользователя проекта проверки (<имя>-*.opt) — и только они."""
    steps: Any = importlib.import_module("check_sources")
    names = ["tpl-check-AllUsers.opt", "TPL-CHECK-user-host.opt", "tpl-library-AllUsers.opt", "tpl-check.json", "x.opt"]
    for name in names:
        (tmp_path / name).write_text("", encoding="utf-8")
    found = [Path(p).name for p in steps.option_files(str(tmp_path / "tpl-check.project"))]
    assert sorted(found) == ["TPL-CHECK-user-host.opt", "tpl-check-AllUsers.opt"]
    assert steps.option_files(str(tmp_path / "missing" / "a.project")) == []


class FakeRef:
    """Ссылка Library Manager: плейсхолдер или обычная (только свойства, которые читает ref_record)."""

    def __init__(self, name: str, placeholder: str | None = None, target: str = "", namespace: str = "") -> None:
        self.name = name
        self.is_placeholder = placeholder is not None
        self.placeholder_name = placeholder
        self.effective_resolution = target or None
        self.default_resolution = target or None
        self.namespace = namespace
        self.qualified_only = False
        self.is_managed = placeholder is None
        self.managed_library = None

    def get_redirection(self) -> None:
        return None


class FakeLibman:
    is_libman = True

    def __init__(self, refs: list[FakeRef] | None = None) -> None:
        self.references = list(refs or [])

    def add_placeholder(self, name: str, target: str) -> None:
        self.references.append(FakeRef("#" + name, name, target, namespace=name))

    def add_library(self, lib: Any) -> None:
        self.references.append(FakeRef(str(lib), namespace="lib"))


class FakeObj:
    def __init__(self, children: list[Any]) -> None:
        self.children = children

    def get_children(self, recursive: bool) -> list[Any]:
        return list(self.children)


class FakeDevice(FakeObj):
    is_device = True

    def __init__(self, proj: FakeProject, app: FakeObj) -> None:
        super().__init__([app])
        self.proj = proj

    def remove(self) -> None:
        self.proj.children.remove(self)


class FakeProject(FakeObj):
    def __init__(self, device_refs: list[FakeRef]) -> None:
        super().__init__([])
        self.device_refs = device_refs
        self.pool = FakeLibman()
        self.added: list[tuple[str, Any]] = []
        self.app: FakeObj | None = None

    def add(self, name: str, device_id: Any) -> None:
        self.added.append((name, device_id))
        self.app = FakeObj([FakeLibman(self.device_refs)])
        self.children.append(FakeDevice(self, self.app))

    @property
    def active_application(self) -> FakeObj | None:
        return self.app if self.children else None

    def get_library_manager(self) -> FakeLibman:
        return self.pool


def test_check_mirrors_device_libraries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ссылки, которые добавляет устройство, копируются в пул проверки, устройство удаляется."""
    steps: Any = importlib.import_module("check_sources")
    monkeypatch.setattr(C, "api", lambda: SimpleNamespace(DeviceID=lambda t, i, v: (t, i, v)))
    device_refs = [
        FakeRef("#IoStandard", "IoStandard", "IoStandard, 3.5.17.0 (System)", namespace="IoStandard"),
        FakeRef("#BreakpointLogging", "BreakpointLogging", "Breakpoint Logging Functions, 3.5.17.0 (3S)", "BPLog"),
        FakeRef("#Broken", "Broken", ""),  # ни во что не разрешается — предупреждение, остальные копируются
        FakeRef("Util, 3.5.17.0 (System)", namespace="Util"),
    ]
    proj = FakeProject(device_refs)
    proj.pool.references.append(FakeRef("#IoStandard", "IoStandard", "IoStandard, 3.5.17.0 (System)", "IoStandard"))
    log = C.Log(None)
    device = {"name": "Device", "type": 4096, "id": "0000 0001", "version": "3.5.17.30"}
    copied = steps.mirror_device_libraries(proj, device, log)
    assert proj.added == [("Device", (4096, "0000 0001", "3.5.17.30"))]
    assert copied == ["#BreakpointLogging -> Breakpoint Logging Functions, 3.5.17.0 (3S)", "Util, 3.5.17.0 (System)"]
    by_name = {r.name: r for r in proj.pool.references}
    assert by_name["#BreakpointLogging"].namespace == "BPLog"  # пространство имён — как у устройства
    assert by_name["Util, 3.5.17.0 (System)"].namespace == "Util"
    assert len([r for r in proj.pool.references if r.name == "#IoStandard"]) == 1  # уже был — не дублируется
    assert proj.children == []  # устройство удалено
    assert len(log.warnings) == 1 and "#Broken" in log.warnings[0]
    # без устройства в задании — ничего; устройство не добавляется — предупреждение и пустой список
    assert steps.mirror_device_libraries(FakeProject(device_refs), None, log) == []

    def no_device(t: int, i: str, v: str) -> None:
        raise RuntimeError("Устройство не найдено")

    monkeypatch.setattr(C, "api", lambda: SimpleNamespace(DeviceID=no_device))
    assert steps.mirror_device_libraries(FakeProject(device_refs), device, log) == []
    assert "не добавлено (Устройство не найдено)" in log.warnings[-1]


# ---------------------------------------------------------------------------
# Запускатель
# ---------------------------------------------------------------------------


def test_launcher_help_runs() -> None:
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "codesys" / "cds.py"), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0
    commands = ("import", "export", "build", "check", "test", "roundtrip", "library", "deps", "runtime", "junit")
    for command in (*commands, "report"):
        assert command in proc.stdout
