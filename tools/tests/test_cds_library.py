"""Тесты библиотек и зависимостей cds.py без CODESYS: config.json (library, libraries, library_repository),
версии и идентичность библиотек (cds_common), имена ссылок, задания library/deps/uninstall, сборка
зависимостей в соседних репозиториях (команда, окружение, проверки), учёт установок и рабочие копии
(git worktree): переменные рабочей копии не читаются из реестра, блокировки и build/ — свои у каждой копии.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

import cds_common as C
from cdshost import cli
from conftest import REPO_ROOT

CONFIG = REPO_ROOT / "tools" / "codesys" / "config.json"


def base_config() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(CONFIG.read_text(encoding="utf-8"))
    return data


def settings_for(root: Path, env: dict[str, str] | None = None, config: dict[str, Any] | None = None) -> cli.Settings:
    environ = {"USERPROFILE": str(root / "home"), "HOME": str(root / "home"), "LOCALAPPDATA": str(root / "lad")}
    environ.update(env or {})
    return cli.Settings(config if config is not None else base_config(), root, cli.make_getenv(environ, registry=False))


def lib(title: str, version: str, company: str = "plc-portfolio", namespace: str = "PL") -> dict[str, Any]:
    return {"title": title, "version": version, "company": company, "namespace": namespace}


def consumer_config(**spec: Any) -> dict[str, Any]:
    """config.json потребителя с библиотекой портфолио plc-process-lib (пример из docs)."""
    data = base_config()
    entry: dict[str, Any] = {
        "namespace": "PL",
        "title_contains": "plc-process-lib",
        "version": "1.0.0.0",
        "build_from_repo": {"env": "PL_REPO", "default": "../plc-process-lib"},
        "install_from": {"env": "PL_LIBRARY", "default": None},
    }
    entry.update(spec)
    data["libraries"]["plc-process-lib"] = entry
    data["modes"]["normal"]["libraries"] = ["plc-process-lib"]
    data["modes"]["test"]["libraries"] = ["counit", "plc-process-lib"]
    return data


def make_library_repo(path: Path, **library: Any) -> Path:
    """Каталог соседнего репозитория-библиотеки: tools/codesys/cds.py и config.json с разделом library."""
    data = base_config()
    data["library"].update(
        {"title": "plc-process-lib", "company": "plc-portfolio", "default_namespace": "PL", "exclude": []}
    )
    data["library"].update(library)
    codesys = path / "tools" / "codesys"
    codesys.mkdir(parents=True)
    (codesys / "cds.py").write_text("# launcher\n", encoding="utf-8")
    (codesys / "config.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# cds_common: версии, идентичность, имена ссылок
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "parsed"),
    [
        ("1.2", (1, 2, 0, 0)),
        ("1.2.3", (1, 2, 3, 0)),
        (" 1.2.3.4 ", (1, 2, 3, 4)),
        ("3.5.17.0", (3, 5, 17, 0)),
        ("*", None),
        ("1", None),
        ("1.2.3.4.5", None),
        ("1.x", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_version(text: str | None, parsed: tuple[int, ...] | None) -> None:
    assert C.parse_version(text) == parsed


@pytest.mark.parametrize(
    ("pin", "version", "ok"),
    [
        ("*", "1.0.0.0", True),
        (None, "2.1", True),
        ("", "2.1", True),
        ("1.0", "1.0.0.0", True),
        ("1.0.0.0", "1.0.0.1", False),
        ("1.0.0.0", "*", False),
        ("*", "not a version", False),
    ],
)
def test_version_matches(pin: str | None, version: str, ok: bool) -> None:
    assert C.version_matches(pin, version) is ok


@pytest.mark.parametrize(
    ("spec", "ok"),
    [
        ({"title": "PLC-Process-Lib"}, True),
        ({"title": "plc-process"}, False),
        ({"title_contains": "process"}, True),
        ({"title_contains": "process", "company": "Other"}, False),
        ({"company": "PLC-PORTFOLIO"}, True),
        ({"namespace": "pl"}, True),  # без title/company — по пространству имён по умолчанию
        ({"namespace": "PLX"}, False),
        ({"title_contains": "process", "namespace": "PLX"}, True),  # namespace ссылки можно переопределить
        ({}, False),
    ],
)
def test_lib_matches_identity(spec: dict[str, Any], ok: bool) -> None:
    assert C.lib_matches_identity(lib("plc-process-lib", "1.0.0.0"), spec) is ok


def test_pick_library_exact_and_newest_by_number() -> None:
    records = [lib("plc-process-lib", v) for v in ("1.9.0.0", "1.10.0.0", "1.2.0.0")] + [lib("other", "9.0.0.0")]

    def version(spec: dict[str, Any]) -> str | None:
        found = C.pick_library(records, spec)
        return None if found is None else str(found["version"])

    assert version({"title": "plc-process-lib", "version": "1.2"}) == "1.2.0.0"
    # '*' — новейшая по номеру версии, а не по строке ('1.9' > '1.10' как строки)
    assert version({"title": "plc-process-lib", "version": "*"}) == "1.10.0.0"
    assert version({"title": "plc-process-lib"}) == "1.10.0.0"
    assert C.pick_library(records, {"title": "plc-process-lib", "version": "2.0.0.0"}) is None
    assert C.pick_library([], {"title": "x"}) is None


def test_pick_library_ambiguous_identity_is_error() -> None:
    records = [lib("plc-process-lib", "1.0.0.0"), lib("plc-process-lib-extra", "1.0.0.0")]
    with pytest.raises(C.StepError) as err:
        C.pick_library(records, {"key": "pl", "title_contains": "plc-process-lib"})
    assert "plc-process-lib-extra" in str(err.value) and "title/company" in str(err.value)
    found = C.pick_library(records, {"key": "pl", "title": "plc-process-lib"})
    assert found is not None and found["title"] == "plc-process-lib"


def test_reference_names() -> None:
    rec = lib("plc-process-lib", "1.0.0.0")
    assert C.spec_reference({"version": "1.0.0.0"}, rec) == "plc-process-lib, 1.0.0.0 (plc-portfolio)"
    assert C.spec_reference({"version": "*"}, rec) == "plc-process-lib, * (plc-portfolio)"
    assert C.spec_reference({}, rec) == "plc-process-lib, * (plc-portfolio)"
    assert C.parse_reference_name("plc-process-lib, * (plc-portfolio)") == {
        "title": "plc-process-lib",
        "version": "*",
        "company": "plc-portfolio",
    }
    counit = C.parse_reference_name("co\u267be - A unittest framework for CODESYS, 1.2.0.0 (www.co5e.org)")
    assert counit == {
        "title": "co\u267be - A unittest framework for CODESYS",
        "version": "1.2.0.0",
        "company": "www.co5e.org",
    }
    assert C.parse_reference_name("A, B, 3.5.17.0 (System)") == {
        "title": "A, B",
        "version": "3.5.17.0",
        "company": "System",
    }
    for bad in ("#Standard", "Standard", "Standard, x (System)", "", None):
        assert C.parse_reference_name(bad) is None


def ref(name: str, placeholder: str | None = None, target: str | None = None, namespace: str = "PL") -> dict[str, Any]:
    return {
        "name": name,
        "placeholder": placeholder,
        "target": target if target is not None else name,
        "namespace": namespace,
        "library": None,
        "resolution": C.parse_reference_name(target if target is not None else name),
    }


def test_ref_identity_and_current() -> None:
    spec = {"title_contains": "plc-process-lib", "version": "1.0.0.0"}
    managed = ref("plc-process-lib, 1.0.0.0 (plc-portfolio)")
    star = ref("plc-process-lib, * (plc-portfolio)")
    other = ref("Standard, 3.5.17.0 (System)", namespace="Standard")
    want = "plc-process-lib, 1.0.0.0 (plc-portfolio)"
    assert C.ref_matches_identity(managed, spec) and C.ref_matches_identity(star, spec)
    assert not C.ref_matches_identity(other, spec)
    assert C.ref_is_current(managed, spec, want)
    assert C.ref_is_current(dict(managed, name=want.upper()), spec, want)
    assert not C.ref_is_current(star, spec, want)  # другая версия — заменить
    holder = ref("#PL", placeholder="plc-process-lib", target=want)
    ph_spec = dict(spec, placeholder="plc-process-lib")
    assert C.ref_matches_identity(holder, ph_spec)
    assert C.ref_is_current(holder, ph_spec, want)
    assert not C.ref_is_current(holder, spec, want)  # нужна обычная ссылка, а это плейсхолдер
    assert not C.ref_is_current(managed, ph_spec, want)  # нужен плейсхолдер
    unresolved = ref("#PL", placeholder="plc-process-lib", target="")
    assert not C.ref_is_current(unresolved, ph_spec, want)
    # плейсхолдер узнаётся по имени, даже если разрешения нет
    assert C.ref_matches_identity(dict(unresolved, resolution=None), ph_spec)


def dep_lib(title: str, version: str, deps: list[str], company: str = "plc-portfolio") -> dict[str, Any]:
    """Запись установленной библиотеки с зависимостями (как C.lib_record)."""
    rec = lib(title, version, company)
    rec.update({"displayname": C.reference_name(title, version, company), "dependencies": deps})
    return rec


def test_missing_dependencies_recursive() -> None:
    pl = dep_lib("plc-process-lib", "1.0.0.0", ["#Standard", "pl-base, 1.0.0.0 (plc-portfolio)"])
    base = dep_lib("pl-base", "1.0.0.0", ["#Standard", "Base Interfaces, * (System)"])
    system = dep_lib("Base Interfaces", "3.5.17.0", [], company="System")
    assert C.missing_dependencies(pl, [pl, base, system]) == []
    # точная версия зависимости: другую установленную CODESYS не возьмёт (проверено на 3.5.17.30)
    assert C.missing_dependencies(pl, [pl, dict(base, version="1.1.0.0"), system]) == [
        "pl-base, 1.0.0.0 (plc-portfolio) (нужна для plc-process-lib, 1.0.0.0 (plc-portfolio))"
    ]
    # зависимость зависимости; '*' — любая версия; плейсхолдеры ('#Standard') не проверяются
    assert C.missing_dependencies(pl, [pl, base]) == [
        "Base Interfaces, * (System) (нужна для pl-base, 1.0.0.0 (plc-portfolio))"
    ]
    assert C.missing_dependencies(pl, [pl, base, dict(system, version="3.5.4.0")]) == []
    # цикл зависимостей не зацикливает проверку
    a = dep_lib("a", "1.0.0.0", ["b, 1.0.0.0 (plc-portfolio)"])
    b = dep_lib("b", "1.0.0.0", ["a, 1.0.0.0 (plc-portfolio)"])
    assert C.missing_dependencies(a, [a, b]) == []
    assert C.missing_dependencies(lib("x", "1.0.0.0"), []) == []  # без поля dependencies


class FakeManagedLib:
    """ManagedLib репозитория CODESYS: только нужные свойства."""

    title = "plc-process-lib"
    company = "plc-portfolio"
    version = "1.0.0.0"
    default_namespace = "PL"
    displayname = "plc-process-lib, 1.0.0.0 (plc-portfolio)"
    dependencies = ("#Standard", "pl-base, 1.0.0.0 (plc-portfolio)")


def test_lib_record_reads_dependencies() -> None:
    rec = C.lib_record(FakeManagedLib())
    assert rec["dependencies"] == ["#Standard", "pl-base, 1.0.0.0 (plc-portfolio)"]
    assert rec["namespace"] == "PL" and rec["displayname"] == "plc-process-lib, 1.0.0.0 (plc-portfolio)"
    assert C.lib_record(object())["dependencies"] == []


def test_resolve_libraries_requires_dependencies_of_library(monkeypatch: pytest.MonkeyPatch) -> None:
    # import_sources — скрипт CODESYS (IronPython 2.7); без CODESYS импортируется, mypy его не проверяет
    steps: Any = importlib.import_module("import_sources")
    pl = dep_lib("plc-process-lib", "1.0.0.0", ["pl-base, 1.0.0.0 (plc-portfolio)"])
    spec = {"key": "pl", "title": "plc-process-lib", "version": "1.0.0.0", "build_from_repo": "C:/w/plc-process-lib"}
    monkeypatch.setattr(C, "installed_libraries", lambda: [pl])
    with pytest.raises(C.StepError) as err:
        steps.resolve_libraries([spec], "System", C.Log(None))
    assert err.value.code == C.EXIT_INTERNAL and err.value.data == {"missing_libraries": ["pl"]}
    assert "нет её зависимостей: pl-base, 1.0.0.0 (plc-portfolio)" in str(err.value)
    monkeypatch.setattr(C, "installed_libraries", lambda: [pl, dep_lib("pl-base", "1.0.0.0", [])])
    resolved = steps.resolve_libraries([spec], "System", C.Log(None))
    assert [rec["title"] for _, rec in resolved] == ["plc-process-lib"]
    assert steps.installed_from_files(resolved) == []


@pytest.mark.parametrize(
    ("info", "redirected", "needs"),
    [
        ("Resolved by placeholder default library", False, True),  # свой плейсхолдер в пуле библиотеки
        ("Разрешено профилем библиотеки", False, False),  # Standard
        (None, True, True),  # разрешён только перенаправлением
        (None, None, False),
    ],
)
def test_placeholder_needs_consumer(info: str | None, redirected: bool | None, needs: bool) -> None:
    steps: Any = importlib.import_module("make_library")  # скрипт CODESYS, без CODESYS импортируется
    assert steps.placeholder_needs_consumer(info, redirected) is needs


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({}, None),
        ({"title": ""}, "library.title"),
        ({"company": "Me (home)"}, "library.company"),
        ({"title": "a/b"}, "library.title"),
        ({"version": "1"}, "library.version"),
        ({"version": None}, "library.version"),
        ({"default_namespace": "1PL"}, "library.default_namespace"),
        ({"default_namespace": ""}, "library.default_namespace"),
        ({"placeholder": "#pl"}, "library.placeholder"),
        ({"placeholder": "plc-process-lib"}, None),
    ],
)
def test_library_problems(change: dict[str, Any], message: str | None) -> None:
    info = {"title": "plc-process-lib", "company": "plc-portfolio", "version": "1.0.0.0", "default_namespace": "PL"}
    info.update(change)
    problems = C.library_problems(info)
    if message is None:
        assert problems == []
    else:
        assert len(problems) == 1 and message in problems[0]


def test_precompile_cache_of_library_differs_from_project() -> None:
    names = [Path(p).name for p in C.precompile_cache_paths(str(Path("b") / "demo.library"))]
    assert names == ["demo_library.precompilecache"]
    assert "demo_project.precompilecache" not in names


def test_step_error_data() -> None:
    exc = C.StepError("нет библиотек", C.EXIT_INTERNAL, data={"missing_libraries": ["pl"]})
    assert exc.code == C.EXIT_INTERNAL and exc.data == {"missing_libraries": ["pl"]}
    assert C.StepError("x").data == {}


def test_run_main_merges_step_error_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = tmp_path / "fake_missing_libs.py"
    module.write_text(
        "import cds_common as C\n\ndef run(ctx, step):\n"
        "    raise C.StepError('нет', C.EXIT_INTERNAL, data={'missing_libraries': ['pl']})\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(C.ACTION_MODULES, "fake_missing", "fake_missing_libs")
    monkeypatch.delitem(sys.modules, "fake_missing_libs", raising=False)
    result = tmp_path / "result.json"
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"result": str(result), "steps": [{"action": "fake_missing"}]}), encoding="utf-8")
    monkeypatch.setenv(C.JOB_ENV, str(job))
    with pytest.raises(SystemExit) as stop:
        C.run_main("fake_missing")
    assert stop.value.code == C.EXIT_INTERNAL
    data = json.loads(result.read_text(encoding="utf-8"))
    assert cli.missing_library_keys(data) == ["pl"]


# ---------------------------------------------------------------------------
# config.json: library, libraries, library_repository
# ---------------------------------------------------------------------------


def repo_library_raw() -> dict[str, Any]:
    """Секция library из config.json этой рабочей копии (в проектах она своя)."""
    cfg_path = Path(__file__).resolve().parents[1] / "codesys" / "config.json"
    raw: dict[str, Any] = json.loads(cfg_path.read_text(encoding="utf-8"))["library"]
    return raw


def test_repo_library_config(tmp_path: Path) -> None:
    raw = repo_library_raw()
    version = raw["version"]["default"] if isinstance(raw["version"], dict) else raw["version"]
    root = tmp_path / "some-checkout"
    lib_cfg = settings_for(root).library_config()
    info = lib_cfg["info"]
    assert info["title"] == raw["title"] and info["company"] == raw["company"]
    assert info["version"] == version and info["default_namespace"] == raw["default_namespace"]
    assert info["released"] is raw["released"] and info["placeholder"] == raw["placeholder"]
    assert lib_cfg["path"] == root / "build" / f"{root.name}.library"
    assert lib_cfg["compiled_path"] == root / "build" / f"{root.name}.compiled-library"
    assert lib_cfg["exclude"] == raw["exclude"] and lib_cfg["libraries"] == raw["libraries"]
    assert lib_cfg["label"] == f"{raw['title']}, {version} ({raw['company']})"
    # название и компания не зависят от каталога рабочей копии (git worktree)
    assert settings_for(tmp_path / "wt-feature").library_config()["info"]["title"] == raw["title"]


def test_library_config_env_and_validation(tmp_path: Path) -> None:
    s = settings_for(tmp_path, {"CDS_LIBRARY_VERSION": "0.2.0.7", "CDS_LIBRARY": str(tmp_path / "out.library")})
    lib_cfg = s.library_config()
    assert lib_cfg["info"]["version"] == "0.2.0.7"
    assert lib_cfg["path"] == tmp_path / "out.library"
    bad = base_config()
    bad["library"]["default_namespace"] = "has space"
    with pytest.raises(cli.CdsError) as err:
        settings_for(tmp_path, config=bad).library_config()
    assert err.value.code == cli.EXIT_USAGE and "default_namespace" in str(err.value)
    bad = base_config()
    bad["library"]["released"] = "yes"
    assert settings_for(tmp_path, config=bad).library_config()["info"]["released"] is True
    del bad["library"]
    with pytest.raises(cli.CdsError) as err:
        settings_for(tmp_path, config=bad).library_config()
    assert err.value.code == cli.EXIT_USAGE


def test_library_spec_paths_and_pins(tmp_path: Path) -> None:
    root = tmp_path / "pump-station"
    s = settings_for(root, config=consumer_config())
    spec = s.library_spec("plc-process-lib")
    assert Path(spec["build_from_repo"]) == tmp_path / "plc-process-lib"  # '../plc-process-lib' от корня, без '..'
    assert spec["build_env"] == "PL_REPO" and spec["install_env"] == "PL_LIBRARY" and spec["install_from"] is None
    assert spec["namespace"] == "PL" and spec["version"] == "1.0.0.0" and spec["key"] == "plc-process-lib"
    other = tmp_path / "elsewhere" / "pl"
    file = tmp_path / "pl.library"
    s2 = settings_for(root, {"PL_REPO": str(other), "PL_LIBRARY": str(file)}, config=consumer_config())
    spec2 = s2.library_spec("plc-process-lib")
    assert spec2["build_from_repo"] == str(other) and spec2["install_from"] == str(file)
    assert settings_for(root, config=consumer_config(version="*")).library_spec("plc-process-lib")["version"] == "*"


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        ({"version": "1.0-beta"}, "version"),
        ({"qualified_only": "yes"}, "qualified_only"),
        ({"title_contains": None, "namespace": None}, "title, title_contains или namespace"),
    ],
)
def test_library_spec_validation(tmp_path: Path, change: dict[str, Any], fragment: str) -> None:
    s = settings_for(tmp_path, config=consumer_config(**change))
    with pytest.raises(cli.CdsError) as err:
        s.library_spec("plc-process-lib")
    assert err.value.code == cli.EXIT_USAGE and fragment in str(err.value)


def test_doc_keys_are_not_libraries(tmp_path: Path) -> None:
    s = settings_for(tmp_path)
    with pytest.raises(cli.CdsError):
        s.library_spec("_doc")
    assert s.referenced_library_keys() == ["counit"]


def test_referenced_library_keys_and_repository(tmp_path: Path) -> None:
    data = consumer_config()
    data["libraries"]["standard"] = {
        "title": "Standard",
        "company": "System",
        "version": "*",
        "placeholder": "Standard",
    }
    data["library"]["libraries"] = ["standard", "plc-process-lib"]
    s = settings_for(tmp_path, config=data)
    assert s.referenced_library_keys() == ["plc-process-lib", "counit", "standard"]
    assert s.library_repository == "System"
    assert settings_for(tmp_path, {"CDS_LIBRARY_REPOSITORY": "Mine"}, config=data).library_repository == "Mine"
    assert [x["key"] for x in s.library_config()["libraries"]] == ["standard", "plc-process-lib"]


def test_import_step_carries_repository(tmp_path: Path) -> None:
    s = settings_for(tmp_path, {"CDS_LIBRARY_REPOSITORY": "Mine"}, config=consumer_config())
    step = cli.import_step(s, False, s.project_path(False))
    assert step["library_repository"] == "Mine"
    assert [x["key"] for x in step["mode_config"]["libraries"]] == ["plc-process-lib"]
    assert [x["key"] for x in step["other_libraries"]] == ["counit"]


def test_library_libraries_join_project_modes(tmp_path: Path) -> None:
    """Проекты приложения и тестов репозитория-библиотеки ссылаются и на library.libraries: src/ тот же."""
    data = consumer_config()
    data["libraries"]["standard"] = {
        "title": "Standard",
        "company": "System",
        "version": "*",
        "placeholder": "Standard",
    }
    data["library"]["libraries"] = ["standard", "plc-process-lib"]
    s = settings_for(tmp_path, config=data)
    assert s.mode_library_keys("normal") == ["plc-process-lib", "standard"]
    assert s.mode_library_keys("test") == ["counit", "plc-process-lib", "standard"]
    test_step = cli.import_step(s, True, s.project_path(True))
    assert [x["key"] for x in test_step["mode_config"]["libraries"]] == ["counit", "plc-process-lib", "standard"]
    assert test_step["other_libraries"] == []
    normal = cli.import_step(s, False, s.project_path(False))
    assert [x["key"] for x in normal["other_libraries"]] == ["counit"]  # library.libraries не удаляются
    with pytest.raises(cli.CdsError) as err:
        s.mode_library_keys("nope")
    assert err.value.code == cli.EXIT_USAGE


# ---------------------------------------------------------------------------
# Задания library, deps, uninstall
# ---------------------------------------------------------------------------


def test_library_step(tmp_path: Path) -> None:
    root = tmp_path / "plc-process-lib"
    s = settings_for(root)
    lib_cfg = s.library_config()
    step = cli.library_step(s, lib_cfg, install=True, compiled=True, released=True)
    assert step["action"] == "library" and step["repo_root"] == str(root)
    assert step["project"] == str(root / "build" / "codesys" / "plc-process-lib-library.project")
    assert step["project"].endswith(".project") and step["library"].endswith(".library")
    assert step["compiled"] == str(root / "build" / "plc-process-lib.compiled-library")
    assert step["install"] == {"compiled": True} and step["repository"] == "System"
    assert step["info"]["released"] is True and lib_cfg["info"]["released"] is False  # конфиг не меняется
    assert step["exclude"] == ["PRG_Main"]
    assert step["log"] == str(root / "build" / "library.log") and step["report"] == str(root / "build" / "library.json")
    plain = cli.library_step(s, lib_cfg, install=False, compiled=False)
    assert plain["compiled"] is None and plain["install"] is None and plain["info"]["released"] is False


def test_deps_and_uninstall_steps(tmp_path: Path) -> None:
    s = settings_for(tmp_path, config=consumer_config())
    specs = [s.library_spec("plc-process-lib")]
    step = cli.deps_step(s, specs, install_missing=True, reinstall=["plc-process-lib"])
    assert step["action"] == "deps" and step["install_missing"] is True and step["reinstall"] == ["plc-process-lib"]
    assert step["specs"][0]["namespace"] == "PL"
    info = {"title": "plc-process-lib", "company": "plc-portfolio"}
    un = cli.uninstall_step(s, info, ["1.0.0.0"])
    assert un["action"] == "uninstall" and un["versions"] == ["1.0.0.0"] and un["repository"] == "System"
    assert cli.uninstall_step(s, info, [])["versions"] == []


# ---------------------------------------------------------------------------
# Зависимости из соседних репозиториев
# ---------------------------------------------------------------------------


def test_dependency_command() -> None:
    cmd = cli.dependency_command("C:/Python/python.exe", Path("C:/w/plc-process-lib"), Path("C:/w/app/build/r.json"))
    assert cmd[0] == "C:/Python/python.exe"
    assert Path(cmd[1]) == Path("C:/w/plc-process-lib/tools/codesys/cds.py")
    assert cmd[2:] == ["library", "--install", "--result", str(Path("C:/w/app/build/r.json"))]


def test_child_environ_drops_checkout_variables() -> None:
    env = {
        "CDS_PROJECT": "C:/a.project",
        "cds_project_name": "x",
        "CDS_LIBRARY_VERSION": "9.0.0.0",
        "CDS_REPO_ROOT": "C:/a",
        "CDS_JOB": "C:/job.json",
        "CODESYS_EXE": "C:/c.exe",
        "PL_REPO": "C:/pl",
        "PATH": "C:/bin",
    }
    child = cli.child_environ(env)
    assert child == {"CODESYS_EXE": "C:/c.exe", "PL_REPO": "C:/pl", "PATH": "C:/bin"}


def test_checkout_variables_are_not_read_from_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_registry_env", lambda name: f"from-registry:{name}")
    getenv = cli.make_getenv({}, registry=True)
    for name in sorted(cli.CHECKOUT_ENV):
        assert getenv(name) is None
    assert getenv("CODESYS_EXE") == "from-registry:CODESYS_EXE"
    assert getenv("PL_REPO") == "from-registry:PL_REPO"
    assert cli.make_getenv({"CDS_PROJECT": "C:/p.project"}, registry=True)("CDS_PROJECT") == "C:/p.project"


def test_dependency_source_info_ignores_our_checkout_variables(tmp_path: Path) -> None:
    repo = make_library_repo(tmp_path / "plc-process-lib")
    info = cli.dependency_source_info(repo, {"CDS_LIBRARY_VERSION": "9.9.9.9", "LOCALAPPDATA": str(tmp_path)})
    assert info["title"] == "plc-process-lib" and info["version"] == "0.1.0.0" and info["default_namespace"] == "PL"
    with pytest.raises(cli.CdsError) as err:
        cli.dependency_source_info(tmp_path / "nothing", {})
    assert err.value.code == cli.EXIT_ENV
    broken = tmp_path / "broken"
    (broken / "tools" / "codesys").mkdir(parents=True)
    (broken / "tools" / "codesys" / "cds.py").write_text("", encoding="utf-8")
    data = base_config()
    del data["library"]
    (broken / "tools" / "codesys" / "config.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(cli.CdsError) as err:
        cli.dependency_source_info(broken, {})
    assert err.value.code == cli.EXIT_ENV and "раздел library" in str(err.value)


def test_dependency_problems() -> None:
    info = {"title": "plc-process-lib", "company": "plc-portfolio", "version": "1.1.0.0", "default_namespace": "PL"}
    spec = {"key": "pl", "title_contains": "plc-process-lib", "version": "1.1.0.0", "namespace": "PL"}
    assert cli.dependency_problems(spec, info) == []
    assert cli.dependency_problems(dict(spec, version="*"), info) == []
    assert cli.dependency_problems(dict(spec, namespace="OTHER"), info) == []  # пространство имён ссылки — своё
    version = cli.dependency_problems(dict(spec, version="1.0.0.0"), info)
    assert len(version) == 1 and "собирает версию 1.1.0.0" in version[0] and "libraries.pl.version" in version[0]
    identity = cli.dependency_problems(dict(spec, title_contains="other-lib"), info)
    assert len(identity) == 1 and "другую библиотеку" in identity[0]


def test_missing_library_keys() -> None:
    result = {"steps": [{"action": "import", "missing_libraries": ["pl", "x"]}, {"missing_libraries": ["x"]}]}
    assert cli.missing_library_keys(result) == ["pl", "x"]
    assert cli.missing_library_keys({"steps": [{"action": "import", "ok": True}]}) == []


@pytest.mark.parametrize(
    ("missing", "with_repo", "allow", "runs", "built"),
    [
        ([], True, True, 1, []),
        (["plc-process-lib"], True, True, 2, ["plc-process-lib"]),
        (["plc-process-lib"], False, True, 1, []),
        (["plc-process-lib"], True, False, 1, []),
    ],
)
def test_run_with_deps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing: list[str],
    with_repo: bool,
    allow: bool,
    runs: int,
    built: list[str],
) -> None:
    config = consumer_config() if with_repo else consumer_config(build_from_repo=None)
    s = settings_for(tmp_path, config=config)
    calls: list[str] = []
    done: list[str] = []

    def run() -> dict[str, Any]:
        calls.append("run")
        if len(calls) == 1 and missing:
            return {"ok": False, "exit_code": 3, "steps": [{"action": "import", "missing_libraries": missing}]}
        return {"ok": True, "exit_code": 0, "steps": []}

    def fake_build(settings: cli.Settings, spec: dict[str, Any]) -> dict[str, Any]:
        done.append(spec["key"])
        return {}

    monkeypatch.setattr(cli, "build_dependency", fake_build)
    result = cli.run_with_deps(s, run, allow)
    assert len(calls) == runs and done == built
    assert result["ok"] is (not missing or runs == 2)


def fake_child(result: dict[str, Any], code: int = 0) -> Any:
    seen: dict[str, Any] = {}

    def run(cmd: list[str], cwd: Path, env: dict[str, str], prefix: str) -> int:
        seen.update({"cmd": cmd, "cwd": cwd, "env": env, "prefix": prefix})
        Path(cmd[cmd.index("--result") + 1]).write_text(json.dumps(result), encoding="utf-8")
        return code

    return run, seen


def test_build_dependency_runs_library_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_library_repo(tmp_path / "plc-process-lib", version="1.0.0.0")
    s = settings_for(tmp_path / "pump-station", config=consumer_config())
    installed = {"displayname": "plc-process-lib, 1.0.0.0 (plc-portfolio)", "title": "plc-process-lib"}
    installed.update({"company": "plc-portfolio", "version": "1.0.0.0", "namespace": "PL"})
    run, seen = fake_child({"ok": True, "installed": installed})
    monkeypatch.setattr(cli, "_run_streamed", run)
    environ = {"CDS_PROJECT": "C:/consumer.project", "CODESYS_EXE": "C:/c.exe", "LOCALAPPDATA": str(tmp_path)}
    data = cli.build_dependency(s, s.library_spec("plc-process-lib"), environ)
    assert data["installed"]["version"] == "1.0.0.0"
    assert seen["cmd"][2:4] == ["library", "--install"]
    assert Path(seen["cwd"]) == Path(s.library_spec("plc-process-lib")["build_from_repo"])
    assert "CDS_PROJECT" not in seen["env"] and seen["env"]["CODESYS_EXE"] == "C:/c.exe"
    assert seen["prefix"] == "[plc-process-lib] "
    result_file = Path(seen["cmd"][-1])
    assert result_file.parent == s.repo_root / "build" / "codesys" / "deps"
    # цепочка сборки зависимостей передаётся дочернему cds.py (защита от циклов)
    assert cli.dependency_chain(seen["env"]) == [cli._chain_key(s.repo_root)]


def test_build_dependency_refuses_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_library_repo(tmp_path / "plc-process-lib", version="1.0.0.0")
    s = settings_for(tmp_path / "pump-station", config=consumer_config())
    monkeypatch.setattr(cli, "_run_streamed", lambda *a: pytest.fail("сборка не должна запускаться"))
    # plc-process-lib уже собирает зависимости и через pump-station снова дошёл бы до себя
    env = {"LOCALAPPDATA": str(tmp_path), cli.DEPS_CHAIN_ENV: str(tmp_path / "plc-process-lib")}
    with pytest.raises(cli.CdsError) as err:
        cli.build_dependency(s, s.library_spec("plc-process-lib"), env)
    assert err.value.code == cli.EXIT_USAGE and "циклическая" in str(err.value)
    assert "plc-process-lib -> pump-station -> plc-process-lib" in str(err.value)
    other = os.pathsep.join([str(tmp_path / "a"), str(tmp_path / "b")])
    assert cli.dependency_chain({cli.DEPS_CHAIN_ENV: other}) == [
        os.path.normcase(str(tmp_path / "a")),
        os.path.normcase(str(tmp_path / "b")),
    ]
    assert cli.dependency_chain({}) == []


def test_build_dependency_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_library_repo(tmp_path / "plc-process-lib", version="1.0.0.0")
    s = settings_for(tmp_path / "pump-station", config=consumer_config())
    spec = s.library_spec("plc-process-lib")
    env = {"LOCALAPPDATA": str(tmp_path)}
    run, _ = fake_child({}, code=1)
    monkeypatch.setattr(cli, "_run_streamed", run)
    with pytest.raises(cli.CdsError) as err:
        cli.build_dependency(s, spec, env)
    assert err.value.code == cli.EXIT_FAILED and "library.log" in str(err.value)
    # таймаут и занятая блокировка дочернего cds.py — с теми же кодами; ошибка его настроек — окружение
    for child_code, code, fragment in (
        (4, cli.EXIT_TIMEOUT, "код 4"),
        (5, cli.EXIT_LOCK, "код 5"),
        (2, cli.EXIT_ENV, "tools/codesys"),
    ):
        run, _ = fake_child({}, code=child_code)
        monkeypatch.setattr(cli, "_run_streamed", run)
        with pytest.raises(cli.CdsError) as err:
            cli.build_dependency(s, spec, env)
        assert err.value.code == code and fragment in str(err.value)
    wrong = {"title": "plc-process-lib", "company": "plc-portfolio", "version": "0.9.0.0"}
    run, _ = fake_child({"installed": wrong})
    monkeypatch.setattr(cli, "_run_streamed", run)
    with pytest.raises(cli.CdsError) as err:
        cli.build_dependency(s, spec, env)
    assert err.value.code == cli.EXIT_ENV
    # версия соседнего репозитория не подходит под закрепление — сборка не запускается
    s2 = settings_for(tmp_path / "pump-station", config=consumer_config(version="2.0.0.0"))
    monkeypatch.setattr(cli, "_run_streamed", lambda *a: pytest.fail("сборка не должна запускаться"))
    with pytest.raises(cli.CdsError) as err:
        cli.build_dependency(s2, s2.library_spec("plc-process-lib"), env)
    assert err.value.code == cli.EXIT_ENV and "закреплена 2.0.0.0" in str(err.value)
    missing = settings_for(tmp_path / "pump-station", {"PL_REPO": str(tmp_path / "none")}, config=consumer_config())
    with pytest.raises(cli.CdsError) as err:
        cli.build_dependency(missing, missing.library_spec("plc-process-lib"), env)
    assert err.value.code == cli.EXIT_ENV and "PL_REPO" in str(err.value)
    itself = settings_for(
        tmp_path / "plc-process-lib", {"PL_REPO": str(tmp_path / "plc-process-lib")}, consumer_config()
    )
    with pytest.raises(cli.CdsError) as err:
        cli.build_dependency(itself, itself.library_spec("plc-process-lib"), env)
    assert err.value.code == cli.EXIT_USAGE


# ---------------------------------------------------------------------------
# Учёт установок (рабочая копия, коммит, отпечаток src/)
# ---------------------------------------------------------------------------


def installed_record(version: str = "1.0.0.0") -> dict[str, Any]:
    return {
        "displayname": f"plc-process-lib, {version} (plc-portfolio)",
        "title": "plc-process-lib",
        "company": "plc-portfolio",
        "version": version,
        "file": "C:/ProgramData/CODESYS/Managed Libraries/plc-portfolio/plc-process-lib/x.library",
        "compiled": False,
    }


def test_install_registry_roundtrip(tmp_path: Path) -> None:
    lad = {"LOCALAPPDATA": str(tmp_path / "lad")}
    a = settings_for(tmp_path / "wt-a", lad)
    b = settings_for(tmp_path / "wt-b", lad)
    (a.repo_root / "src").mkdir(parents=True)
    (a.repo_root / "src" / "a.st").write_text("x", encoding="utf-8")
    assert cli.install_registry_path(a) == tmp_path / "lad" / "plc-tools" / "codesys-libraries.json"
    assert cli.record_install(a, installed_record(), "abc1234") is None
    assert cli.record_install(a, installed_record(), "abc1235") is None  # та же рабочая копия — без предупреждения
    warning = cli.record_install(b, installed_record(), None)
    assert warning is not None and str(a.repo_root) in warning
    libs = cli.load_install_registry(cli.install_registry_path(a))
    assert list(libs) == ["plc-portfolio|plc-process-lib|1.0.0.0"]
    assert libs["plc-portfolio|plc-process-lib|1.0.0.0"]["checkout"] == str(b.repo_root)
    cli.forget_installs(a, ["plc-process-lib, 1.0.0.0 (plc-portfolio)", "garbage"])
    assert cli.load_install_registry(cli.install_registry_path(a)) == {}
    assert cli.registry_key("C", "T", "1.2") == "c|t|1.2.0.0"


def test_install_provenance_warnings(tmp_path: Path) -> None:
    lad = {"LOCALAPPDATA": str(tmp_path / "lad")}
    library_repo = tmp_path / "plc-process-lib"
    (library_repo / "src").mkdir(parents=True)
    (library_repo / "src" / "F.st").write_text("v1", encoding="utf-8")
    lib_settings = settings_for(library_repo, lad)
    cli.record_install(lib_settings, installed_record(), "abc1234")
    consumer = settings_for(tmp_path / "pump-station", dict(lad, PL_REPO=str(library_repo)), consumer_config())
    spec = consumer.library_spec("plc-process-lib")
    entry = {"title": "plc-process-lib", "company": "plc-portfolio", "version": "1.0.0.0"}
    lines = cli.install_provenance(consumer, spec, entry)
    assert len(lines) == 1 and "abc1234" in lines[0]
    (library_repo / "src" / "F.st").write_text("v2", encoding="utf-8")
    lines = cli.install_provenance(consumer, spec, entry)
    assert len(lines) == 2 and "изменились после установки" in lines[1] and "--rebuild" in lines[1]
    other = settings_for(tmp_path / "pump-station", dict(lad, PL_REPO=str(tmp_path / "pl-wt")), consumer_config())
    lines = cli.install_provenance(other, other.library_spec("plc-process-lib"), entry)
    assert "другой рабочей копии" in lines[1]
    assert cli.install_provenance(consumer, spec, dict(entry, version="9.0.0.0")) == []


# ---------------------------------------------------------------------------
# Команды library и deps (CODESYS подменён)
# ---------------------------------------------------------------------------


def library_result(installed: dict[str, Any] | None, ok: bool = True) -> dict[str, Any]:
    step = {
        "action": "library",
        "ok": ok,
        "library": "C:/r/build/r.library",
        "compiled": None,
        "installed": installed,
        "errors": 0 if ok else 2,
        "warnings": 0,
        "messages": [],
    }
    return {"ok": ok, "exit_code": 0 if ok else 1, "steps": [step]}


def test_cmd_library_installs_and_writes_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = settings_for(tmp_path / "plc-process-lib")
    jobs: list[dict[str, Any]] = []

    def fake_run(settings: cli.Settings, script: str, job: dict[str, Any], label: str, **kw: Any) -> dict[str, Any]:
        jobs.append({"script": script, "job": job, "label": label})
        return library_result(installed_record())

    monkeypatch.setattr(cli, "run_codesys", fake_run)
    out = tmp_path / "res" / "r.json"
    args = cli.build_parser().parse_args(["library", "--install", "--compiled", "--result", str(out)])
    assert cli.cmd_library(s, args) == cli.EXIT_OK
    assert jobs[0]["script"] == "make_library.py" and jobs[0]["job"]["steps"][0]["install"] == {"compiled": True}
    summary = json.loads(out.read_text(encoding="utf-8"))
    assert summary["ok"] is True and summary["installed"]["version"] == "1.0.0.0"
    assert cli.load_install_registry(cli.install_registry_path(s))  # установка учтена
    assert not (s.repo_root / "build" / "codesys" / "cds.lock.owner").exists()  # блокировки сняты


def test_cmd_library_failed_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = settings_for(tmp_path / "plc-process-lib")
    monkeypatch.setattr(cli, "run_codesys", lambda *a, **k: library_result(None, ok=False))
    out = tmp_path / "r.json"
    args = cli.build_parser().parse_args(["library", "--install", "--result", str(out)])
    assert cli.cmd_library(s, args) == cli.EXIT_FAILED
    assert json.loads(out.read_text(encoding="utf-8"))["ok"] is False
    assert cli.load_install_registry(cli.install_registry_path(s)) == {}


def test_cmd_library_removes_stale_compiled_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = settings_for(tmp_path / "plc-process-lib")
    compiled = s.library_config()["compiled_path"]
    compiled.parent.mkdir(parents=True)
    compiled.write_text("прошлая сборка", encoding="utf-8")
    monkeypatch.setattr(cli, "run_codesys", lambda *a, **k: library_result(None))
    assert cli.cmd_library(s, cli.build_parser().parse_args(["library", "--compiled"])) == cli.EXIT_OK
    assert compiled.exists()  # с --compiled файл перезаписывает сама сборка
    assert cli.cmd_library(s, cli.build_parser().parse_args(["library"])) == cli.EXIT_OK
    assert not compiled.exists()


@pytest.mark.parametrize("argv", [["library", "--uninstall", "--install"], ["library", "--all-versions"]])
def test_cmd_library_bad_flags(tmp_path: Path, argv: list[str]) -> None:
    with pytest.raises(cli.CdsError) as err:
        cli.cmd_library(settings_for(tmp_path), cli.build_parser().parse_args(argv))
    assert err.value.code == cli.EXIT_USAGE


def test_cmd_library_uninstall(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = settings_for(tmp_path / "plc-process-lib")
    cli.record_install(s, dict(installed_record(), title="plc-repo-template", displayname="x"), None)
    jobs: list[dict[str, Any]] = []

    def fake_run(settings: cli.Settings, script: str, job: dict[str, Any], label: str, **kw: Any) -> dict[str, Any]:
        jobs.append(job)
        step = {"action": "uninstall", "ok": True, "removed": ["plc-repo-template, 1.0.0.0 (plc-portfolio)"]}
        return {"ok": True, "exit_code": 0, "steps": [dict(step, left=[], repository="System")]}

    monkeypatch.setattr(cli, "run_codesys", fake_run)
    args = cli.build_parser().parse_args(["library", "--uninstall", "--all-versions"])
    assert cli.cmd_library(s, args) == cli.EXIT_OK
    assert jobs[0]["steps"][0]["versions"] == [] and jobs[0]["steps"][0]["title"] == repo_library_raw()["title"]
    assert cli.load_install_registry(cli.install_registry_path(s)) == {}


def deps_result(found: bool) -> dict[str, Any]:
    entries = [
        {"key": "plc-process-lib", "found": found, "installed_versions": ["0.9.0.0"]},
        {
            "key": "counit",
            "found": True,
            "displayname": "coUnit",
            "version": "1.2.0.0",
            "installed_versions": ["1.2.0.0"],
        },
    ]
    return {"ok": True, "exit_code": 0, "steps": [{"action": "deps", "ok": True, "libraries": entries}]}


def test_cmd_deps_builds_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    s = settings_for(tmp_path / "pump-station", config=consumer_config())
    monkeypatch.setattr(cli, "run_codesys", lambda *a, **k: deps_result(found=False))
    built: list[str] = []

    def fake_build(settings: cli.Settings, spec: dict[str, Any]) -> dict[str, Any]:
        built.append(spec["key"])
        return {"installed": installed_record()}

    monkeypatch.setattr(cli, "build_dependency", fake_build)
    assert cli.cmd_deps(s, cli.build_parser().parse_args(["deps"])) == cli.EXIT_OK
    assert built == ["plc-process-lib"]
    assert "собрана в" in capsys.readouterr().out
    assert cli.cmd_deps(s, cli.build_parser().parse_args(["deps", "--check"])) == cli.EXIT_FAILED
    assert built == ["plc-process-lib"]  # --check ничего не собирает


def test_cmd_deps_missing_without_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = settings_for(tmp_path / "pump-station", config=consumer_config(build_from_repo=None))
    monkeypatch.setattr(cli, "run_codesys", lambda *a, **k: deps_result(found=False))
    with pytest.raises(cli.CdsError) as err:
        cli.cmd_deps(s, cli.build_parser().parse_args(["deps"]))
    assert err.value.code == cli.EXIT_ENV and "plc-process-lib" in str(err.value)


def test_cmd_deps_rebuild_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = settings_for(tmp_path / "pump-station", config=consumer_config())
    monkeypatch.setattr(cli, "run_codesys", lambda *a, **k: deps_result(found=True))
    built: list[str] = []

    def fake_build(settings: cli.Settings, spec: dict[str, Any]) -> dict[str, Any]:
        built.append(spec["key"])
        return {}

    monkeypatch.setattr(cli, "build_dependency", fake_build)
    assert cli.cmd_deps(s, cli.build_parser().parse_args(["deps"])) == cli.EXIT_OK
    assert built == []
    assert cli.cmd_deps(s, cli.build_parser().parse_args(["deps", "--rebuild", "plc-process-lib"])) == cli.EXIT_OK
    assert built == ["plc-process-lib"]


def test_cmd_deps_library_without_its_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Библиотека есть, а её зависимости нет: --check — код 1, deps — пересборка в build_from_repo."""
    result = deps_result(found=True)
    result["steps"][0]["libraries"][0].update(
        {
            "displayname": "plc-process-lib, 1.0.0.0 (plc-portfolio)",
            "missing_dependencies": ["pl-base, 1.0.0.0 (plc-portfolio) (нужна для plc-process-lib)"],
        }
    )
    monkeypatch.setattr(cli, "run_codesys", lambda *a, **k: result)
    built: list[str] = []

    def fake_build(settings: cli.Settings, spec: dict[str, Any]) -> dict[str, Any]:
        built.append(spec["key"])
        return {"installed": installed_record()}

    monkeypatch.setattr(cli, "build_dependency", fake_build)
    s = settings_for(tmp_path / "pump-station", config=consumer_config())
    assert cli.cmd_deps(s, cli.build_parser().parse_args(["deps", "--check"])) == cli.EXIT_FAILED
    assert built == [] and "НЕТ её зависимостей: pl-base" in capsys.readouterr().out
    assert cli.cmd_deps(s, cli.build_parser().parse_args(["deps"])) == cli.EXIT_OK
    assert built == ["plc-process-lib"]
    no_repo = settings_for(tmp_path / "pump-station", config=consumer_config(build_from_repo=None))
    with pytest.raises(cli.CdsError) as err:
        cli.cmd_deps(no_repo, cli.build_parser().parse_args(["deps"]))
    assert err.value.code == cli.EXIT_ENV and "plc-process-lib" in str(err.value)


def test_print_steps_shows_libraries_installed_from_file(capsys: pytest.CaptureFixture[str]) -> None:
    item = "plc-process-lib, 1.0.0.0 (plc-portfolio) <- C:/rel/plc-process-lib.library"
    cli._print_steps({"steps": [{"action": "import", "ok": True, "installed_libraries": [item]}]})
    assert f"(install_from): {item}" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Рабочие копии (git worktree): build/ и блокировки
# ---------------------------------------------------------------------------


def test_worktrees_have_own_build_and_locks(tmp_path: Path) -> None:
    env = {"LOCALAPPDATA": str(tmp_path / "lad")}
    main = settings_for(tmp_path / "plc-repo-template", env)
    feature = settings_for(tmp_path / "plc-repo-template-feature", env)
    assert main.project_path(False).parent != feature.project_path(False).parent
    assert cli.repo_lock(main, "t").path != cli.repo_lock(feature, "t").path
    assert cli.repo_lock(main, "t").path == tmp_path / "plc-repo-template" / "build" / "codesys" / "cds.lock"
    assert cli.runtime_lock(main, "t").path == cli.runtime_lock(feature, "t").path
    assert cli.library_lock(main, "t").path == cli.library_lock(feature, "t").path
    assert cli.library_lock(main, "t").path == tmp_path / "lad" / "plc-tools" / "codesys-library-repo.lock"
    assert main.library_config()["path"].parent == main.repo_root / "build"


def test_annotate_library_messages(tmp_path: Path) -> None:
    root = tmp_path / "r"
    fb = root / "src" / "POUs" / "Counters" / "FB_X"
    fb.mkdir(parents=True)
    (fb / "FB_X.decl.st").write_text("FUNCTION_BLOCK FB_X\nVAR\n    i : INT;\nEND_VAR\n", encoding="utf-8")
    (fb / "FB_X.impl.st").write_text("i := 1;\ni := 2;\n", encoding="utf-8")
    s = settings_for(root)
    msg = {"severity": "Error", "object": "Counters.FB_X", "position": "Строка 2, Столбец 1 (Реализ.)", "text": "x"}
    result = {"steps": [{"action": "library", "messages": [msg]}]}
    (root / "build").mkdir()
    (root / "build" / "library.json").write_text(json.dumps({"messages": []}), encoding="utf-8")
    cli.annotate_build(s, result, "library")
    assert msg["source"] == "src/POUs/Counters/FB_X/FB_X.impl.st:2"
    saved = json.loads((root / "build" / "library.json").read_text(encoding="utf-8"))
    assert saved["messages"][0]["source"] == "src/POUs/Counters/FB_X/FB_X.impl.st:2"


def test_parser_has_library_commands() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["deps", "a", "b", "--rebuild"])
    assert args.keys == ["a", "b"] and args.rebuild and not args.check
    for command in ("import", "build", "test", "roundtrip", "library"):
        assert parser.parse_args([command, "--no-deps"]).no_deps is True
