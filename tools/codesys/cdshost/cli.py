"""cds.py — единственная команда для человека: импорт, сборка, тесты и экспорт CODESYS из консоли.

Реализация командной строки tools/codesys/cds.py (сам cds.py — короткий запускатель, совместимый
по синтаксису с IronPython 2.7, как все файлы tools/codesys/*.py). Python 3.11+, только стандартная
библиотека. Скрипты CODESYS (import_sources.py, export_sources.py,
build.py, run_tests.py — IronPython 2.7) запускаются как
    "<CODESYS.exe>" --profile="<профиль>" --noUI --runscript="<скрипт>"
одной строкой с кавычками после '=' (иначе CODESYS не видит профиль), а параметры получают через
файл задания JSON (путь — в переменной окружения CDS_JOB): аргументы скриптов CODESYS ненадёжны.

Подкоманды:
    import [--tests] [--clean] [--force]   исходники -> проект (build/<имя>.project или <имя>-tests.project)
    export [--tests] [--to DIR]            проект -> раскладка src/ (и tests/)
    build [--tests] [--no-import]          импорт и полная сборка, сообщения -> build/build.log, build.json
    test [--restart-runtime]               импорт с тестами, сборка, прогон coUnit в рантайме -> build/test-results.json
    roundtrip                              импорт в чистый проект -> экспорт во временный каталог -> сравнение
    library [--install] [--compiled]       src/ -> библиотека build/<имя>.library (+ .compiled-library), установка
    library --uninstall [--all-versions]   удаление библиотеки этого репозитория из репозитория библиотек
    deps [KEY...] [--rebuild] [--check]    библиотеки из config.json: проверка, установка, сборка в соседних репо
    runtime start|stop|status|restart|init пользовательский процесс CODESYS Control Win V3
    junit [--results F] [--out F]          build/test-results.json -> build/junit.xml
    report [--results F] [--doc F]         раздел последнего прогона в docs/TEST_REPORT.md

Коды выхода: 0 — успех; 1 — проверка не прошла (ошибки раскладки или сборки, упавшие тесты, дифф
roundtrip); 2 — неверные аргументы или config.json; 3 — окружение (нет CODESYS, рантайма, файла);
4 — таймаут; 5 — не удалось взять блокировку.

Настройки — tools/codesys/config.json (между репозиториями отличается только он), переменные
окружения — tools/README.md, ручные шаги — docs/MANUAL_STEPS.md.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import difflib
import glob
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from types import TracebackType
from typing import IO, Any

import cds_common as C
import stlayout as L

TOOLS_CODESYS = Path(__file__).resolve().parent.parent
DEFAULT_REPO_ROOT = TOOLS_CODESYS.parent.parent
CONFIG_NAME = "config.json"
JOB_ENV = "CDS_JOB"
STATE_FILE = "build/codesys/state.json"
WORK_DIR = "build/codesys"

# Переменные, привязанные к рабочей копии (checkout): читаются только из окружения процесса,
# не из HKCU\Environment. Заданные через setx, они действовали бы сразу на все рабочие копии —
# параллельные git worktree одного репозитория писали бы в один проект или собирали бы библиотеку
# одной версии. Их же не наследует cds.py соседнего репозитория (build_from_repo).
CHECKOUT_ENV = frozenset(
    {
        "CDS_REPO_ROOT",
        "CDS_CONFIG",
        "CDS_PROJECT_NAME",
        "CDS_PROJECT",
        "CDS_TEST_PROJECT",
        "CDS_LIBRARY",
        "CDS_COMPILED_LIBRARY",
        "CDS_LIBRARY_VERSION",
        JOB_ENV,
    }
)
LIBRARY_INFO_KEYS = (
    "title",
    "company",
    "version",
    "default_namespace",
    "placeholder",
    "author",
    "description",
    "released",
)
LIBRARY_PATH_KEYS = (("install_from", "install_env"), ("build_from_repo", "build_env"))
# Цепочка репозиториев, которые сейчас собирают зависимости (через os.pathsep): её передаёт
# cds.py соседнему репозиторию (build_from_repo), чтобы цикл библиотек A -> B -> A дал ошибку,
# а не бесконечную цепочку процессов
DEPS_CHAIN_ENV = "CDS_DEPS_CHAIN"

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_ENV = 3
EXIT_TIMEOUT = 4
EXIT_LOCK = 5

REPORT_BEGIN = "<!-- cds:test-report:begin (раздел обновляет `python tools/codesys/cds.py report`) -->"
REPORT_END = "<!-- cds:test-report:end -->"
RUNTIME_IMAGE = "CODESYSControlService.exe"

Getenv = Callable[[str], "str | None"]


class CdsError(Exception):
    """Ошибка с понятным сообщением и кодом выхода."""

    def __init__(self, message: str, code: int = EXIT_FAILED) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Переменные окружения и config.json
# ---------------------------------------------------------------------------


def _registry_env(name: str) -> str | None:
    """Переменная пользователя из HKCU\\Environment (setx не меняет окружение запущенных процессов)."""
    if sys.platform != "win32":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, kind = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    if not isinstance(value, str) or not value:
        return None
    if kind == winreg.REG_EXPAND_SZ:
        value = os.path.expandvars(value)
    return value


def make_getenv(environ: Mapping[str, str] | None = None, registry: bool = True) -> Getenv:
    """Функция чтения переменной: окружение процесса, затем (Windows) реестр пользователя.

    Переменные рабочей копии (CHECKOUT_ENV) из реестра не читаются.
    """
    env = os.environ if environ is None else environ

    def getenv(name: str) -> str | None:
        value = env.get(name)
        if value:
            return value
        if sys.platform == "win32" and environ is None:
            # Windows: имена переменных без учёта регистра
            for key, val in env.items():
                if key.upper() == name.upper() and val:
                    return val
        if not registry or name.upper() in CHECKOUT_ENV:
            return None
        return _registry_env(name)

    return getenv


def child_environ(environ: Mapping[str, str]) -> dict[str, str]:
    """Окружение для cds.py другого репозитория: без переменных рабочей копии (CHECKOUT_ENV)."""
    return {k: v for k, v in environ.items() if k.upper() not in CHECKOUT_ENV}


def _chain_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path.resolve())))


def dependency_chain(environ: Mapping[str, str]) -> list[str]:
    """Репозитории, которые уже собирают зависимости выше по цепочке (DEPS_CHAIN_ENV)."""
    raw = next((v for k, v in environ.items() if k.upper() == DEPS_CHAIN_ENV), "")
    return [os.path.normcase(os.path.normpath(p)) for p in raw.split(os.pathsep) if p]


_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_()]*)\}")
_PLACEHOLDER_RE = re.compile(r"\{(repo|repo_name|name|runtime_dir)\}")


class Settings:
    """Разрешённые настройки: config.json + переменные окружения + подстановки."""

    def __init__(self, config: Mapping[str, Any], repo_root: Path, getenv: Getenv) -> None:
        self.config = config
        self.repo_root = repo_root
        self.getenv = getenv
        self._cache: dict[str, Any] = {}

    # --- разрешение значений -------------------------------------------------

    def node(self, dotted: str) -> Any:
        node: Any = self.config
        for part in dotted.split("."):
            if not isinstance(node, Mapping) or part not in node:
                raise CdsError(f"config.json: нет ключа {dotted} / missing key {dotted}", EXIT_USAGE)
            node = node[part]
        return node

    def expand(self, text: str) -> str:
        def var(match: re.Match[str]) -> str:
            name = match.group(1)
            value = self.getenv(name)
            if value is None:
                raise CdsError(
                    f"переменная окружения {name} не задана (нужна для {text}) / environment variable {name} not set",
                    EXIT_ENV,
                )
            return value

        def placeholder(match: re.Match[str]) -> str:
            key = match.group(1)
            if key == "repo":
                return str(self.repo_root)
            if key == "repo_name":
                return self.repo_root.name
            if key == "name":
                return str(self.value("project.name"))
            return str(self.path("runtime.dir"))

        result = _VAR_RE.sub(var, text)
        result = _PLACEHOLDER_RE.sub(placeholder, result)
        if result.startswith("~"):
            home = self.getenv("USERPROFILE") or self.getenv("HOME") or str(Path.home())
            result = home + result[1:]
        return result

    def _raw(self, dotted: str) -> tuple[Any, str | None]:
        node = self.node(dotted)
        if isinstance(node, Mapping) and ("env" in node or "default" in node):
            env_name = node.get("env")
            if env_name:
                value = self.getenv(str(env_name))
                if value is not None:
                    return value, str(env_name)
            return node.get("default"), None
        return node, None

    def value(self, dotted: str) -> Any:
        """Значение настройки (строки — с подстановками)."""
        if dotted in self._cache:
            return self._cache[dotted]
        raw, _ = self._raw(dotted)
        if isinstance(raw, str):
            raw = self.expand(raw)
        self._cache[dotted] = raw
        return raw

    def number(self, dotted: str) -> float:
        raw = self.value(dotted)
        try:
            return float(raw)
        except (TypeError, ValueError):
            raise CdsError(f"config.json/окружение: {dotted} = {raw!r} — не число / not a number", EXIT_USAGE) from None

    def path(self, dotted: str, must_exist: bool = False) -> Path:
        """Путь из настройки; список кандидатов — первый существующий; относительный — от корня репозитория."""
        raw, env_name = self._raw(dotted)
        if raw is None:
            raise CdsError(f"не задан путь {dotted} / path {dotted} is not configured", EXIT_ENV)
        candidates = raw if isinstance(raw, list) else [raw]
        resolved: list[Path] = []
        errors: list[str] = []
        for cand in candidates:
            try:
                text = self.expand(str(cand))
            except CdsError as exc:
                errors.append(str(exc))
                continue
            path = Path(text)
            if not path.is_absolute():
                path = self.repo_root / path
            resolved.append(path)
            if path.exists():
                return path
        if must_exist or (isinstance(raw, list) and len(raw) > 1):
            source = f"переменная {env_name}" if env_name else f"config.json: {dotted}"
            tried = ", ".join(str(p) for p in resolved) or "; ".join(errors)
            raise CdsError(f"не найден файл ({source}): {tried} / file not found", EXIT_ENV)
        if not resolved:
            raise CdsError("; ".join(errors), EXIT_ENV)
        return resolved[0]

    # --- готовые значения -------------------------------------------------

    @property
    def codesys_exe(self) -> Path:
        return self.path("codesys.exe", must_exist=True)

    @property
    def profile(self) -> str:
        return str(self.value("codesys.profile"))

    def project_path(self, tests: bool) -> Path:
        return self.path("project.test_path" if tests else "project.path")

    @property
    def tests_folder(self) -> str:
        return str(self.value("project.tests_folder"))

    def device(self) -> dict[str, Any]:
        return {
            "name": str(self.value("device.name")),
            "type": int(self.number("device.type")),
            "id": str(self.value("device.id")),
            "version": str(self.value("device.version")),
        }

    def device_label(self) -> str:
        dev = self.device()
        return f"{self.value('device.title')} ({dev['type']} / {dev['id']} / {dev['version']})"

    def library_spec(self, key: str) -> dict[str, Any]:
        """Описание библиотеки-зависимости libraries.<key> с разрешёнными путями и проверкой.

        Ключи: namespace (пространство имён ссылки в проекте), title / title_contains / company
        (какая библиотека), version (точная '1.0.0.0' или '*' — новейшая установленная),
        placeholder (ссылка-плейсхолдер), qualified_only, install_from (файл .library),
        build_from_repo (репозиторий, где её собирает cds.py library --install), label.
        """
        libs = self.node("libraries")
        if key not in libs or key.startswith("_"):
            raise CdsError(f"config.json: библиотека {key} не описана в libraries / unknown library {key}", EXIT_USAGE)
        node = libs[key]
        if not isinstance(node, Mapping):
            raise CdsError(f"config.json: libraries.{key} — ожидался объект / expected an object", EXIT_USAGE)
        path_keys = {path_key for path_key, _ in LIBRARY_PATH_KEYS}
        spec: dict[str, Any] = {
            k: self.value(f"libraries.{key}.{k}") for k in node if k not in path_keys and not k.startswith("_")
        }
        for path_key, env_key in LIBRARY_PATH_KEYS:
            sub = node.get(path_key)
            spec[env_key] = sub.get("env") if isinstance(sub, Mapping) else None
            spec[path_key] = None
            if sub is not None and self._raw(f"libraries.{key}.{path_key}")[0]:
                spec[path_key] = os.path.normpath(str(self.path(f"libraries.{key}.{path_key}")))
        spec["key"] = key
        version = spec.get("version")
        if version is not None and not C.is_newest_pin(version) and C.parse_version(version) is None:
            raise CdsError(
                f"config.json: libraries.{key}.version = {version!r}: нужна версия из 2-4 чисел (1.0.0.0) или '*' "
                "(новейшая) / invalid version pin",
                EXIT_USAGE,
            )
        if spec.get("qualified_only") is not None and not isinstance(spec["qualified_only"], bool):
            raise CdsError(f"config.json: libraries.{key}.qualified_only — true или false", EXIT_USAGE)
        if not any(spec.get(k) for k in ("title", "title_contains", "company", "namespace")):
            raise CdsError(
                f"config.json: libraries.{key}: нужен title, title_contains или namespace / library identity missing",
                EXIT_USAGE,
            )
        return spec

    def own_library_keys(self) -> list[str]:
        """Ключи libraries, на которые ссылается библиотека этого репозитория (library.libraries)."""
        lib_node = self.config.get("library")
        own = lib_node.get("libraries", []) if isinstance(lib_node, Mapping) else []
        return [str(k) for k in own]

    def mode_library_keys(self, mode: str) -> list[str]:
        """Библиотеки проекта режима: modes.<режим>.libraries и library.libraries, без повторов.

        library.libraries нужны и проектам приложения и тестов этого репозитория: в них
        компилируются те же объекты src/, что и в библиотеке (иначе тесты библиотеки не соберутся:
        «Неизвестный тип: 'TON'», проверено на 3.5.17.30).
        """
        modes = self.node("modes")
        if mode not in modes:
            raise CdsError(f"config.json: нет режима {mode} / no mode {mode}", EXIT_USAGE)
        keys: list[str] = []
        for key in [str(k) for k in modes[mode].get("libraries", [])] + self.own_library_keys():
            if key not in keys:
                keys.append(key)
        return keys

    def mode_config(self, mode: str) -> dict[str, Any]:
        keys = self.mode_library_keys(mode)  # заодно проверяет, что режим есть
        return {
            "tasks": list(self.node("modes")[mode].get("tasks", [])),
            "libraries": [self.library_spec(k) for k in keys],
        }

    def other_libraries(self, mode: str) -> list[dict[str, Any]]:
        modes = self.node("modes")
        mine = set(self.mode_library_keys(mode))
        keys = sorted({str(k) for m in modes.values() for k in m.get("libraries", [])} - mine)
        return [self.library_spec(k) for k in keys]

    def referenced_library_keys(self) -> list[str]:
        """Ключи libraries, на которые ссылаются режимы и сама библиотека (library.libraries), без повторов."""
        keys: list[str] = []
        for key in [str(k) for m in self.node("modes").values() for k in m.get("libraries", [])]:
            if key not in keys:
                keys.append(key)
        for key in self.own_library_keys():
            if key not in keys:
                keys.append(key)
        return keys

    @property
    def library_repository(self) -> str:
        """Репозиторий библиотек CODESYS для установки (по имени; пусто — первый в списке)."""
        if "library_repository" not in self.config:
            return "System"
        return str(self.value("library_repository.name") or "")

    def library_config(self) -> dict[str, Any]:
        """Раздел library: Project Information, пути, исключения и ссылки библиотеки этого репозитория."""
        node = self.node("library")
        info: dict[str, Any] = {k: (self.value(f"library.{k}") if k in node else None) for k in LIBRARY_INFO_KEYS}
        info["version"] = str(info["version"]) if info["version"] is not None else None
        released = info.get("released")
        if isinstance(released, str):
            released = released.strip().lower() in ("1", "true", "yes")
        info["released"] = bool(released)
        problems = C.library_problems(info)
        if problems:
            raise CdsError("config.json: " + "; ".join(problems), EXIT_USAGE)
        return {
            "info": info,
            "path": self.path("library.path"),
            "compiled_path": self.path("library.compiled_path"),
            "exclude": [str(x) for x in node.get("exclude", [])],
            "libraries": [self.library_spec(k) for k in node.get("libraries", [])],
            "label": C.reference_name(info["title"], info["version"], info["company"]),
        }


def load_config(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CdsError(f"нет файла настроек {path} / config not found", EXIT_USAGE) from None
    except json.JSONDecodeError as exc:
        raise CdsError(f"{path}: неверный JSON / invalid JSON: {exc}", EXIT_USAGE) from None
    if not isinstance(data, dict):
        raise CdsError(f"{path}: ожидался объект JSON / expected a JSON object", EXIT_USAGE)
    return data


def make_settings(repo_root: Path | None = None, environ: Mapping[str, str] | None = None) -> Settings:
    getenv = make_getenv(environ)
    root = repo_root or Path(getenv("CDS_REPO_ROOT") or DEFAULT_REPO_ROOT)
    config_path = Path(getenv("CDS_CONFIG") or (root / "tools" / "codesys" / CONFIG_NAME))
    return Settings(load_config(config_path), root.resolve(), getenv)


# ---------------------------------------------------------------------------
# Командная строка CODESYS и файл задания
# ---------------------------------------------------------------------------


def build_cmdline(exe: str | Path, profile: str, script: str | Path) -> str:
    """Командная строка CODESYS одной строкой: кавычки после '=' обязательны буквально.

    Список аргументов subprocess превратил бы --profile="..." в "--profile=...", и CODESYS
    ответил бы «Для работы в режиме --noUI необходимо определить профиль» (проверено на 3.5.17.30).
    """
    parts = {"exe": str(exe), "profile": profile, "script": str(script)}
    for name, value in parts.items():
        if '"' in value or "\n" in value or "\r" in value:
            raise CdsError(f"недопустимый символ в {name}: {value!r} / invalid character", EXIT_USAGE)
        if not value:
            raise CdsError(f"пустое значение {name} / empty {name}", EXIT_USAGE)
    return f'"{parts["exe"]}" --profile="{parts["profile"]}" --noUI --runscript="{parts["script"]}"'


def write_job(path: Path, job: Mapping[str, Any]) -> None:
    """Файл задания для скриптов CODESYS (UTF-8, LF)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(job, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _oem_encoding() -> str:
    if sys.platform == "win32":
        import ctypes

        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    else:
        return "utf-8"


def _kill_tree(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True, check=False)
    else:  # pragma: no cover - CODESYS только под Windows
        with contextlib.suppress(OSError):
            os.kill(pid, 9)


def run_codesys(
    settings: Settings,
    script: str,
    job: dict[str, Any],
    label: str,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """Запускает скрипт CODESYS с заданием; возвращает результат (job['result'])."""
    work = settings.repo_root / WORK_DIR
    work.mkdir(parents=True, exist_ok=True)
    job_path = work / f"job-{label}.json"
    result_path = work / f"result-{label}.json"
    stdout_path = work / f"{label}.stdout.log"
    with contextlib.suppress(FileNotFoundError):
        result_path.unlink()
    job = dict(job)
    job["result"] = str(result_path)
    write_job(job_path, job)
    cmdline = build_cmdline(settings.codesys_exe, settings.profile, TOOLS_CODESYS / script)
    env = dict(os.environ)
    env[JOB_ENV] = str(job_path)
    timeout = timeout_s if timeout_s is not None else settings.number("codesys.timeout_s")
    started = time.time()
    print(f"[cds] CODESYS {settings.profile}: {script} ({label}) ...", flush=True)
    proc = subprocess.Popen(
        cmdline,
        cwd=str(settings.repo_root),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid)
        out, _ = proc.communicate()
        stdout_path.write_text(out.decode(_oem_encoding(), "replace"), encoding="utf-8")
        raise CdsError(
            f"CODESYS не завершился за {timeout:.0f} с (проект открыт в IDE? диалог в noUI?) — процесс остановлен; "
            f"вывод: {stdout_path} / CODESYS timed out",
            EXIT_TIMEOUT,
        ) from None
    elapsed = time.time() - started
    stdout_path.write_text(out.decode(_oem_encoding(), "replace"), encoding="utf-8", newline="\n")
    if not result_path.exists():
        raise CdsError(
            f"CODESYS завершился с кодом {proc.returncode} за {elapsed:.0f} с, но не записал результат {result_path}; "
            f"вывод: {stdout_path} / no result file",
            EXIT_ENV,
        )
    result: dict[str, Any] = json.loads(result_path.read_text(encoding="utf-8"))
    result["process_exit_code"] = proc.returncode
    result["elapsed_s"] = round(elapsed, 1)
    if proc.returncode != result.get("exit_code"):
        print(
            f"[cds] предупреждение: код выхода CODESYS {proc.returncode}, в результате {result.get('exit_code')}",
            flush=True,
        )
    return result


# ---------------------------------------------------------------------------
# Блокировки
# ---------------------------------------------------------------------------


class FileLock:
    """Межпроцессная блокировка файлом (msvcrt.locking / fcntl.flock); снимается и при смерти процесса."""

    def __init__(self, path: Path, timeout_s: float, poll_s: float = 0.5, purpose: str = "") -> None:
        self.path = path
        self.timeout_s = timeout_s
        self.poll_s = poll_s
        self.purpose = purpose
        self._handle: IO[bytes] | None = None

    @property
    def owner_path(self) -> Path:
        return self.path.with_name(self.path.name + ".owner")

    def _try_lock(self, handle: IO[bytes]) -> bool:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return False
            return True
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return False
            return True

    def _unlock(self, handle: IO[bytes]) -> None:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            with contextlib.suppress(OSError):
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            with contextlib.suppress(OSError):
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def owner(self) -> str:
        try:
            return self.owner_path.read_text(encoding="utf-8").strip()
        except OSError:
            return "неизвестно"

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")
        deadline = time.monotonic() + self.timeout_s
        announced = False
        while not self._try_lock(handle):
            if time.monotonic() >= deadline:
                handle.close()
                raise CdsError(
                    f"блокировка {self.path} занята дольше {self.timeout_s:.0f} с (владелец: {self.owner()}) "
                    "/ lock timeout",
                    EXIT_LOCK,
                )
            if not announced:
                print(f"[cds] ожидание блокировки {self.path} (владелец: {self.owner()}) ...", flush=True)
                announced = True
            time.sleep(self.poll_s)
        self._handle = handle
        info = {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "purpose": self.purpose,
            "since": dt.datetime.now().isoformat(timespec="seconds"),
        }
        with contextlib.suppress(OSError):
            self.owner_path.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")

    def release(self) -> None:
        if self._handle is None:
            return
        with contextlib.suppress(OSError):
            self.owner_path.unlink()
        self._unlock(self._handle)
        self._handle.close()
        self._handle = None

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.release()


def runtime_lock(settings: Settings, purpose: str) -> FileLock:
    """Глобальная блокировка рантайма: один рантайм на машину, запуски из разных репозиториев ждут друг друга."""
    return FileLock(settings.path("lock.path"), settings.number("lock.timeout_s"), purpose=purpose)


def repo_lock(settings: Settings, purpose: str) -> FileLock:
    """Блокировка рабочей копии: один процесс CODESYS на проекты этого checkout (build/ у каждого свой).

    Параллельные git worktree одного репозитория — разные каталоги, у каждого свои build/ и
    блокировка; общие на машину — только рантайм и репозиторий библиотек (свои блокировки).
    """
    return FileLock(
        settings.repo_root / WORK_DIR / "cds.lock",
        settings.number("lock.timeout_s"),
        purpose=f"{purpose} {settings.repo_root}",
    )


def library_lock(settings: Settings, purpose: str) -> FileLock:
    """Глобальная блокировка репозитория библиотек CODESYS: установка и удаление — по одному процессу.

    Порядок взятия блокировок везде один: рабочая копия -> рантайм -> репозиторий библиотек;
    cds.py соседнего репозитория (build_from_repo) запускается, когда этот процесс их не держит.
    """
    if "library_repository" in settings.config:
        path = settings.path("library_repository.lock")
    else:
        path = settings.path("lock.path").with_name("codesys-library-repo.lock")
    return FileLock(path, settings.number("lock.timeout_s"), purpose=f"{purpose} {settings.repo_root}")


# ---------------------------------------------------------------------------
# Состояние проекта: защита правок из IDE от перезаписи импортом и исходников — экспортом
# ---------------------------------------------------------------------------


def layout_subdirs(tests: bool) -> tuple[str, ...]:
    return ("src", "tests") if tests else ("src",)


def _fingerprint(path: Path) -> dict[str, Any] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return {"mtime_ns": st.st_mtime_ns, "size": st.st_size}


def sources_digest(root: Path, subdirs: Sequence[str]) -> str:
    """SHA-256 файлов *.st раскладки (пути и содержимое) — признак «исходники не менялись»."""
    digest = hashlib.sha256()
    for sub in subdirs:
        base = root / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.st")):
            digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
            digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def _state(settings: Settings) -> dict[str, Any]:
    path = settings.repo_root / STATE_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _entry(settings: Settings, project: Path) -> dict[str, Any]:
    entry = _state(settings).get(str(project))
    return entry if isinstance(entry, dict) else {}


def record_project_state(settings: Settings, project: Path, subdirs: Sequence[str]) -> None:
    """Запоминает отпечаток проекта и исходников после успешного import/export."""
    data = _state(settings)
    fp = _fingerprint(project)
    if fp is None:
        data.pop(str(project), None)
    else:
        data[str(project)] = {"project": fp, "sources": sources_digest(settings.repo_root, subdirs)}
    path = settings.repo_root / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check_project_state(settings: Settings, project: Path, force: bool) -> None:
    """Отказ импорта, если проект менялся вне cds.py (сохранён в IDE) после последнего import/export."""
    if force or not project.exists():
        return
    recorded = _entry(settings, project).get("project")
    current = _fingerprint(project)
    if recorded is not None and current is not None and recorded != current:
        raise CdsError(
            f"проект {project} изменён вне cds.py (сохранён в IDE?): импорт перезапишет правки. "
            "Сначала выгрузите их: cds.py export [--tests], либо повторите с --force / "
            "project was modified outside cds.py; export first or use --force",
            EXIT_FAILED,
        )


def check_sources_state(settings: Settings, project: Path, subdirs: Sequence[str], force: bool) -> None:
    """Отказ экспорта в репозиторий, если исходники менялись после последнего import/export проекта.

    Экспорт записывает раскладку целиком и удаляет файлы *.st, которых нет в проекте: файлы,
    добавленные в src/ после импорта, пропали бы.
    """
    if force:
        return
    recorded = _entry(settings, project).get("sources")
    if recorded is None:
        return
    if recorded != sources_digest(settings.repo_root, subdirs):
        raise CdsError(
            f"исходники {', '.join(subdirs)} изменились после последнего import/export проекта {project}: "
            "экспорт перезаписал бы их. Сначала cds.py import (правки из IDE при этом пропадут) или сравните "
            "вручную: cds.py export --to <каталог>; перезапись — с --force / "
            "sources changed since last import; export --to DIR or use --force",
            EXIT_FAILED,
        )


# ---------------------------------------------------------------------------
# Шаги заданий
# ---------------------------------------------------------------------------


def import_step(
    settings: Settings,
    tests: bool,
    project: Path,
    clean: bool = False,
    log_dir: Path | None = None,
    name: str = "import",
    reopen: bool = False,
) -> dict[str, Any]:
    mode = "test" if tests else "normal"
    logs = log_dir or (settings.repo_root / "build")
    return {
        "action": "import",
        "repo_root": str(settings.repo_root),
        "with_tests": tests,
        "tests_folder": settings.tests_folder,
        "mode": mode,
        "mode_config": settings.mode_config(mode),
        "other_libraries": settings.other_libraries(mode),
        "project": str(project),
        "device": settings.device(),
        "library_repository": settings.library_repository,
        "clean": clean,
        "reopen": reopen,
        "log": str(logs / f"{name}.log"),
        "report": str(logs / f"{name}.json"),
    }


def library_step(
    settings: Settings, lib: Mapping[str, Any], install: bool, compiled: bool, released: bool = False
) -> dict[str, Any]:
    """Шаг library: src/ -> build/<имя>.library (+ .compiled-library) и, по флагу, установка."""
    info = dict(lib["info"])
    if released:
        info["released"] = True
    build = settings.repo_root / "build"
    return {
        "action": "library",
        "repo_root": str(settings.repo_root),
        "tests_folder": settings.tests_folder,
        # временный проект: projects.create всегда создаёт .project, библиотека — save_as(.library)
        "project": str(settings.repo_root / WORK_DIR / f"{settings.value('project.name')}-library.project"),
        "library": str(lib["path"]),
        "compiled": str(lib["compiled_path"]) if compiled else None,
        "info": info,
        "libraries": list(lib["libraries"]),
        "exclude": list(lib["exclude"]),
        "repository": settings.library_repository,
        "install": {"compiled": compiled} if install else None,
        "log": str(build / "library.log"),
        "report": str(build / "library.json"),
    }


def deps_step(
    settings: Settings, specs: Sequence[Mapping[str, Any]], install_missing: bool, reinstall: Sequence[str] = ()
) -> dict[str, Any]:
    """Шаг deps: есть ли библиотеки в репозиториях; отсутствующие — установка из install_from."""
    build = settings.repo_root / "build"
    return {
        "action": "deps",
        "specs": [dict(s) for s in specs],
        "install_missing": install_missing,
        "reinstall": list(reinstall),
        "repository": settings.library_repository,
        "log": str(build / "deps.log"),
        "report": str(build / "deps.json"),
    }


def uninstall_step(settings: Settings, info: Mapping[str, Any], versions: Sequence[str]) -> dict[str, Any]:
    """Шаг uninstall: удаление версий библиотеки (пустой список — всех) из репозитория."""
    return {
        "action": "uninstall",
        "title": info["title"],
        "company": info["company"],
        "versions": list(versions),
        "repository": settings.library_repository,
        "log": str(settings.repo_root / "build" / "library-uninstall.log"),
    }


def build_step(settings: Settings, project: Path) -> dict[str, Any]:
    return {
        "action": "build",
        "project": str(project),
        "log": str(settings.repo_root / "build" / "build.log"),
        "report": str(settings.repo_root / "build" / "build.json"),
    }


def export_step(
    settings: Settings, project: Path, out_root: Path, tests: bool, log_dir: Path | None = None
) -> dict[str, Any]:
    logs = log_dir or (settings.repo_root / "build")
    return {
        "action": "export",
        "project": str(project),
        "out_root": str(out_root),
        "with_tests": tests,
        "tests_folder": settings.tests_folder,
        "log": str(logs / "export.log"),
        "report": str(logs / "export.json"),
    }


def test_meta(settings: Settings) -> dict[str, Any]:
    return {
        "codesys_version": str(settings.value("codesys.version")),
        "profile": settings.profile,
        "device": settings.device_label(),
        "runtime": str(settings.value("runtime.title")),
        "framework": str(settings.value("tests.framework")),
        "repo": settings.repo_root.name,
    }


def test_step(settings: Settings, project: Path) -> dict[str, Any]:
    return {
        "action": "test",
        "project": str(project),
        "credentials": str(settings.path("runtime.credentials")),
        "runtime": {
            "gateway_name": str(settings.value("runtime.gateway.name")),
            "gateway_host": str(settings.value("runtime.gateway.host")),
            "gateway_port": int(settings.number("runtime.gateway.port")),
            "device_address": str(settings.value("runtime.device_address")),
            "device_port": int(settings.number("runtime.port")),
        },
        "tests": {
            "runner": str(settings.value("tests.runner")),
            "timeout_s": settings.number("tests.timeout_s"),
            "poll_ms": int(settings.number("tests.poll_ms")),
            "max_suites": int(settings.number("tests.max_suites")),
            "max_tests_per_suite": int(settings.number("tests.max_tests_per_suite")),
        },
        "meta": test_meta(settings),
        "log": str(settings.repo_root / "build" / "test.log"),
        "results": str(settings.path("tests.results")),
    }


_POS_LINE_RE = re.compile(r"(\d+)")
_POS_DECL_RE = re.compile(r"Объявл|Decl", re.IGNORECASE)
_POS_IMPL_RE = re.compile(r"Реализ|Impl", re.IGNORECASE)


def layout_objects(repo_root: Path) -> list[L.StObject]:
    """Объекты раскладки src/ и tests/ (для привязки сообщений компилятора к файлам)."""
    objects: list[L.StObject] = []
    for subdir in ("src", "tests"):
        objects.extend(L.scan(str(repo_root), subdir).objects)
    return objects


def source_location(obj_path: str | None, position: str | None, objects: Sequence[L.StObject]) -> str | None:
    """Файл раскладки и строка для сообщения компилятора: 'src/POUs/F_Clamp/F_Clamp.impl.st:16'.

    obj_path — путь объекта из сообщения (папки через точку, затем объект, метод/свойство,
    аксессор: 'Tests.FB_X_Test.Run', 'FB_Example.Count.Get'); position — текст позиции IDE
    ('Строка 16, Столбец 1 (Реализ.)', 'Строка 26 (Объявл.)'). Строка в CODESYS совпадает со
    строкой файла: объявление и тело лежат в раскладке отдельными файлами.
    """
    if not obj_path:
        return None
    index = {o.name.lower(): o for o in objects}
    parts = obj_path.split(".")
    obj = None
    rest: list[str] = []
    for i, part in enumerate(parts):
        if part.lower() in index:
            obj = index[part.lower()]
            rest = parts[i + 1 :]
            break
    if obj is None:
        return None
    section = None
    line = None
    if position:
        if _POS_DECL_RE.search(position):
            section = "decl"
        elif _POS_IMPL_RE.search(position):
            section = "impl"
        match = _POS_LINE_RE.search(position)
        line = int(match.group(1)) if match else None
    files = [rel for rel, _ in L.object_files(obj)]
    base = obj.rel_dir()
    wanted: str | None = None
    if not rest:
        if obj.kind in (L.KIND_POU,) and section == "impl":
            wanted = f"{base}/{obj.name}.impl.st"
        else:
            wanted = files[0]
    elif len(rest) == 1:
        member = rest[0].lower()
        for method in obj.methods:
            if method.name.lower() == member:
                suffix = "method.impl.st" if section == "impl" else "method.decl.st"
                wanted = f"{base}/{method.name}.{suffix}"
        for prop in obj.properties:
            if prop.name.lower() == member:
                wanted = f"{base}/{prop.name}.prop.decl.st"
    elif len(rest) == 2:
        for prop in obj.properties:
            if prop.name.lower() == rest[0].lower() and rest[1].lower() in ("get", "set"):
                kind = "decl" if section == "decl" else "impl"
                wanted = f"{base}/{prop.name}.{rest[1].lower()}.{kind}.st"
    if wanted is None or wanted not in files:
        return None
    return f"{wanted}:{line}" if line else wanted


def annotate_build(settings: Settings, result: Mapping[str, Any], action: str = "build") -> None:
    """Добавляет к сообщениям компилятора поле source (файл:строка) и переписывает build/<action>.json.

    action — шаг с сообщениями: build (сборка приложения) или library (проверка пула библиотеки:
    пути объектов там от корня проекта — 'Motors.FB_X', их разбирает тот же source_location).
    """
    step = next((s for s in result.get("steps", []) if s.get("action") == action), None)
    if not step or not step.get("messages"):
        return
    try:
        objects = layout_objects(settings.repo_root)
    except (OSError, UnicodeDecodeError):
        return
    for msg in step["messages"]:
        msg["source"] = source_location(msg.get("object"), msg.get("position"), objects)
    report = settings.repo_root / "build" / f"{action}.json"
    if report.exists():
        data = json.loads(report.read_text(encoding="utf-8"))
        data["messages"] = step["messages"]
        text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        report.write_text(text, encoding="utf-8", newline="\n")


def _step(result: Mapping[str, Any], action: str, index: int = 0) -> dict[str, Any]:
    found = [s for s in result.get("steps", []) if s.get("action") == action]
    return dict(found[index]) if len(found) > index else {}


def _print_messages(step: Mapping[str, Any]) -> None:
    for msg in step.get("messages", []):
        if msg.get("severity") in ("Error", "FatalError", "Warning"):
            where = f" [{msg['object']}{', ' + msg['position'] if msg.get('position') else ''}]"
            if not msg.get("object"):
                where = ""
            prefix = f"{msg['source']}: " if msg.get("source") else ""
            print(f"[cds]   {prefix}{msg['severity']} {msg.get('code') or ''} {msg.get('text')}{where}")


def _print_steps(result: Mapping[str, Any]) -> None:
    for step in result.get("steps", []):
        action = step.get("action")
        status = "OK" if step.get("ok") else "ОШИБКА"
        detail = ""
        if action == "import":
            detail = (
                f"создано {len(step.get('created', []))}, обновлено {len(step.get('updated', []))}, "
                f"удалено {len(step.get('removed', []))}, перемещено {len(step.get('moved', []))}, "
                f"без изменений {step.get('unchanged', 0)}"
            )
            for bucket in ("removed",):
                for item in step.get(bucket, []):
                    print(f"[cds]   удалено: {item}")
            for item in step.get("created", []) + step.get("updated", []):
                if str(item).startswith("LIBRARY"):
                    print(f"[cds]   {item}")
        elif action == "build":
            detail = f"ошибок {step.get('errors')}, предупреждений {step.get('warnings')}"
            _print_messages(step)
        elif action == "library":
            detail = (
                f"объектов {step.get('objects', 0)}, ошибок проверки пула {step.get('errors', '-')}, "
                f"предупреждений {step.get('warnings', '-')}"
            )
            _print_messages(step)
            for warn in step.get("log_warnings", []):
                print(f"[cds]   предупреждение: {warn}")
        elif action == "deps":
            found = [e for e in step.get("libraries", []) if e.get("found")]
            detail = f"найдено {len(found)} из {len(step.get('libraries', []))}"
        elif action == "uninstall":
            detail = f"удалено {len(step.get('removed', []))}"
        elif action == "export":
            detail = (
                f"файлов {step.get('files')}, объектов src {step.get('objects_src')}, tests {step.get('objects_tests')}"
            )
        elif action == "test":
            totals = step.get("totals") or {}
            if totals:
                detail = (
                    f"наборов {totals.get('suites')}, тестов {totals.get('tests')}, "
                    f"пройдено {totals.get('passed')}, упало {totals.get('failed')}, "
                    f"пропущено {totals.get('skipped')}"
                )
            else:
                detail = "тесты не выполнялись"
        print(f"[cds] {action}: {status} ({detail}, {step.get('duration_s')} с)")
        for item in step.get("installed_libraries") or []:
            print(f"[cds]   установлена в репозиторий библиотек (install_from): {item}")
        warnings = step.get("warnings")
        for warn in warnings if isinstance(warnings, list) else []:
            print(f"[cds]   предупреждение: {warn}")
        if step.get("error"):
            print(f"[cds]   {step['error']}".rstrip())
    if result.get("error"):
        print(f"[cds] ошибка скрипта CODESYS: {result['error']}".rstrip())


def _finish(result: Mapping[str, Any]) -> int:
    _print_steps(result)
    code = int(result.get("exit_code", EXIT_FAILED))
    if code == 0:
        return EXIT_OK
    return EXIT_FAILED if code == 1 else EXIT_ENV


# ---------------------------------------------------------------------------
# Библиотеки-зависимости: сборка в соседних репозиториях, учёт установок
# ---------------------------------------------------------------------------


def missing_library_keys(result: Mapping[str, Any]) -> list[str]:
    """Ключи libraries, которых шаг import/library не нашёл в репозиториях (поле missing_libraries)."""
    keys: list[str] = []
    for step in result.get("steps", []):
        for key in step.get("missing_libraries") or []:
            if str(key) not in keys:
                keys.append(str(key))
    return keys


def dependency_command(python: str, repo: Path, result_path: Path) -> list[str]:
    """Сборка и установка библиотеки в её репозитории: <python> <repo>/tools/codesys/cds.py library --install."""
    return [python, str(repo / "tools" / "codesys" / "cds.py"), "library", "--install", "--result", str(result_path)]


def dependency_source_info(repo: Path, environ: Mapping[str, str]) -> dict[str, Any]:
    """Project Information библиотеки, которую собирает репозиторий repo (его config.json: library).

    Настройки читаются с окружением без переменных рабочей копии (CHECKOUT_ENV): например,
    CDS_LIBRARY_VERSION этого процесса не должен менять версию соседней библиотеки.
    """
    launcher = repo / "tools" / "codesys" / "cds.py"
    if not launcher.is_file():
        raise CdsError(f"нет {launcher}: это не репозиторий с tools/codesys / not a library repository", EXIT_ENV)
    try:
        info = make_settings(repo, environ=child_environ(environ)).library_config()["info"]
    except CdsError as exc:
        raise CdsError(
            f"{repo}: раздел library в tools/codesys/config.json не читается ({exc}) — репозиторий не настроен "
            "как библиотека или его инструменты устарели / dependency repository has no library config",
            EXIT_ENV,
        ) from None
    return dict(info)


def dependency_problems(spec: Mapping[str, Any], info: Mapping[str, Any]) -> list[str]:
    """Соберёт ли репозиторий (info — его library) ту библиотеку и версию, которую ждёт spec."""
    rec = {"title": info.get("title"), "company": info.get("company"), "namespace": info.get("default_namespace")}
    key = spec.get("key")
    problems: list[str] = []
    if not C.lib_matches_identity(rec, dict(spec)):
        problems.append(
            f"собирает «{info.get('title')}» ({info.get('company')}), а libraries.{key} описывает другую библиотеку "
            "(title, title_contains, company)"
        )
    if not C.version_matches(spec.get("version"), info.get("version")):
        problems.append(
            f"собирает версию {info.get('version')}, а закреплена {spec.get('version')}: переключите этот "
            f"репозиторий на нужную версию (git checkout <тег>) или измените libraries.{key}.version"
        )
    return problems


def _run_streamed(cmd: Sequence[str], cwd: Path, env: Mapping[str, str], prefix: str) -> int:
    """Дочерний cds.py: вывод построчно с префиксом, код выхода. Таймауты — у самого дочернего процесса."""
    proc = subprocess.Popen(
        list(cmd),
        cwd=str(cwd),
        env=dict(env),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.stdout is not None:
        for raw in proc.stdout:
            print(f"{prefix}{raw.decode('utf-8', 'replace').rstrip()}", flush=True)
    return proc.wait()


def build_dependency(
    settings: Settings, spec: Mapping[str, Any], environ: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Собирает и устанавливает библиотеку spec в её репозитории (build_from_repo); результат дочернего cds.py.

    Перед сборкой — проверка по config.json того репозитория: та ли библиотека и подходит ли её
    версия под закрепление (иначе сборка была бы напрасной). Дочерний cds.py берёт блокировки своей
    рабочей копии и репозитория библиотек.
    """
    env = os.environ if environ is None else environ
    key = str(spec["key"])
    if not spec.get("build_from_repo"):
        raise CdsError(f"libraries.{key}: не задан build_from_repo / no build_from_repo", EXIT_USAGE)
    repo = Path(str(spec["build_from_repo"]))
    if not repo.is_dir():
        where = spec.get("build_env") or f"libraries.{key}.build_from_repo"
        raise CdsError(
            f"libraries.{key}: нет каталога {repo} — клонируйте репозиторий библиотеки или задайте путь в {where}",
            EXIT_ENV,
        )
    if repo.resolve() == settings.repo_root.resolve():
        raise CdsError(f"libraries.{key}.build_from_repo указывает на этот же репозиторий", EXIT_USAGE)
    chain = dependency_chain(env) + [_chain_key(settings.repo_root)]
    if _chain_key(repo) in chain:
        names = " -> ".join(Path(p).name for p in [*chain, _chain_key(repo)])
        raise CdsError(
            f"циклическая зависимость библиотек: {names} (libraries.*.build_from_repo, library.libraries) — "
            "библиотека не может через другие зависеть от себя / dependency cycle",
            EXIT_USAGE,
        )
    info = dependency_source_info(repo, env)
    problems = dependency_problems(spec, info)
    if problems:
        raise CdsError(f"библиотека {key} из {repo}: " + "; ".join(problems), EXIT_ENV)
    result_path = settings.repo_root / WORK_DIR / "deps" / f"{key}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(FileNotFoundError):
        result_path.unlink()
    label = C.reference_name(info["title"], info["version"], info["company"])
    print(f"[cds] {key}: сборка и установка {label} в {repo}", flush=True)
    child_env = child_environ(env)
    child_env[DEPS_CHAIN_ENV] = os.pathsep.join(chain)
    code = _run_streamed(dependency_command(sys.executable, repo, result_path), repo, child_env, f"[{key}] ")
    if code != EXIT_OK:
        log = repo / "build" / "library.log"
        if code == EXIT_FAILED:
            why = f"ошибки проверки библиотеки — сообщения выше, журнал: {log}"
        elif code == EXIT_USAGE:
            why = (
                "ошибка аргументов или настроек того репозитория — сообщение выше (если у него нет команды library, "
                "обновите его tools/codesys)"
            )
        else:
            why = f"журнал: {log}"
        raise CdsError(
            f"сборка библиотеки {key} в {repo} не удалась (код {code}): {why} / dependency build failed",
            code if code in (EXIT_FAILED, EXIT_TIMEOUT, EXIT_LOCK) else EXIT_ENV,
        )
    try:
        data: dict[str, Any] = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise CdsError(f"{repo}: cds.py library не записал результат {result_path}", EXIT_ENV) from None
    installed = data.get("installed") or {}
    if not (
        C.lib_matches_identity(installed, dict(spec))
        and C.version_matches(spec.get("version"), installed.get("version"))
    ):
        raise CdsError(f"{repo}: установлена {installed.get('displayname')}, а libraries.{key} ждёт другую", EXIT_ENV)
    return data


def run_with_deps(settings: Settings, run: Callable[[], dict[str, Any]], allow: bool) -> dict[str, Any]:
    """Задание с импортом; если нет библиотек, которые собираются из соседних репозиториев, — сборка и повтор.

    run выполняется под своими блокировками; зависимости собираются между двумя запусками, когда
    этот процесс блокировок не держит. Повтор — один: если библиотеки так и не нашлись, ошибка
    второго запуска выводится как есть.
    """
    result = run()
    keys = missing_library_keys(result)
    if not keys or not allow:
        return result
    specs = [settings.library_spec(k) for k in keys]
    if not all(s.get("build_from_repo") for s in specs):
        return result
    print(
        f"[cds] в репозиториях CODESYS нет библиотек (или их зависимостей) {', '.join(keys)} — сборка в соседних "
        "репозиториях (отключить: --no-deps)",
        flush=True,
    )
    for spec in specs:
        build_dependency(settings, spec)
    print("[cds] зависимости установлены — повтор", flush=True)
    return run()


def install_registry_path(settings: Settings) -> Path:
    if "library_repository" in settings.config:
        return settings.path("library_repository.registry")
    return settings.path("lock.path").with_name("codesys-libraries.json")


def registry_key(company: Any, title: Any, version: Any) -> str:
    parsed = C.parse_version(version)
    text = ".".join(str(p) for p in parsed) if parsed else str(version)
    return f"{company}|{title}|{text}".lower()


def load_install_registry(path: Path) -> dict[str, Any]:
    """Учёт установок cds.py library --install: «компания|название|версия» -> откуда установлена."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    libs = data.get("libraries") if isinstance(data, dict) else None
    return libs if isinstance(libs, dict) else {}


def save_install_registry(path: Path, libs: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps({"libraries": dict(libs)}, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def record_install(settings: Settings, installed: Mapping[str, Any], commit: str | None) -> str | None:
    """Запись об установке (рабочая копия, коммит, отпечаток src/); предупреждение, если та же версия
    была установлена из другой рабочей копии. Вызывается под блокировкой репозитория библиотек."""
    path = install_registry_path(settings)
    libs = load_install_registry(path)
    key = registry_key(installed.get("company"), installed.get("title"), installed.get("version"))
    previous = libs.get(key) if isinstance(libs.get(key), dict) else {}
    libs[key] = {
        "displayname": installed.get("displayname"),
        "checkout": str(settings.repo_root),
        "commit": commit,
        "sources": sources_digest(settings.repo_root, ("src",)),
        "file": installed.get("file"),
        "compiled": bool(installed.get("compiled")),
        "installed_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    save_install_registry(path, libs)
    other = (previous or {}).get("checkout")
    if other and os.path.normcase(os.path.normpath(other)) != os.path.normcase(
        os.path.normpath(str(settings.repo_root))
    ):
        return f"{installed.get('displayname')} была установлена из другой рабочей копии {other} — заменена"
    return None


def forget_installs(settings: Settings, displaynames: Sequence[str]) -> None:
    path = install_registry_path(settings)
    libs = load_install_registry(path)
    changed = False
    for name in displaynames:
        parsed = C.parse_reference_name(name)
        if parsed and libs.pop(registry_key(parsed["company"], parsed["title"], parsed["version"]), None) is not None:
            changed = True
    if changed:
        save_install_registry(path, libs)


def install_provenance(settings: Settings, spec: Mapping[str, Any], entry: Mapping[str, Any]) -> list[str]:
    """Откуда установлена найденная версия и предупреждения: другая рабочая копия, изменились исходники."""
    libs = load_install_registry(install_registry_path(settings))
    rec = libs.get(registry_key(entry.get("company"), entry.get("title"), entry.get("version")))
    if not isinstance(rec, dict):
        return []
    commit = rec.get("commit") or "без коммита git"
    lines = [f"установлена cds.py из {rec.get('checkout')} @ {commit} ({rec.get('installed_at')})"]
    src = spec.get("build_from_repo")
    checkout = rec.get("checkout")
    if src and checkout and os.path.normcase(os.path.normpath(checkout)) != os.path.normcase(os.path.normpath(src)):
        lines.append(
            f"предупреждение: установлена из другой рабочей копии, не из {src} — пересобрать: "
            f"cds.py deps --rebuild {spec['key']}"
        )
    elif src and rec.get("sources") and Path(src).is_dir() and sources_digest(Path(src), ("src",)) != rec["sources"]:
        lines.append(
            f"предупреждение: исходники {Path(src) / 'src'} изменились после установки — пересобрать: "
            f"cds.py deps --rebuild {spec['key']}"
        )
    return lines


# ---------------------------------------------------------------------------
# Подкоманды: import, export, build, test, roundtrip, library, deps
# ---------------------------------------------------------------------------


def cmd_import(settings: Settings, args: argparse.Namespace) -> int:
    project = settings.project_path(args.tests)

    def run() -> dict[str, Any]:
        with repo_lock(settings, "import"):
            check_project_state(settings, project, args.force or args.clean)
            job = {"steps": [import_step(settings, args.tests, project, clean=args.clean)]}
            result = run_codesys(settings, "import_sources.py", job, "import")
            if result.get("ok"):
                record_project_state(settings, project, layout_subdirs(args.tests))
                print(f"[cds] проект: {project}")
            return result

    return _finish(run_with_deps(settings, run, not args.no_deps))


def cmd_export(settings: Settings, args: argparse.Namespace) -> int:
    project = settings.project_path(args.tests)
    out_root = Path(args.to).resolve() if args.to else settings.repo_root
    if not project.exists():
        raise CdsError(f"нет проекта {project}: сначала cds.py import{' --tests' if args.tests else ''}", EXIT_ENV)
    with repo_lock(settings, "export"):
        if out_root == settings.repo_root:
            check_sources_state(settings, project, layout_subdirs(args.tests), args.force)
        job = {"steps": [export_step(settings, project, out_root, args.tests)]}
        result = run_codesys(settings, "export_sources.py", job, "export")
        if result.get("ok") and out_root == settings.repo_root:
            record_project_state(settings, project, layout_subdirs(args.tests))
            print("[cds] проверьте изменения: git status / git diff --stat")
    return _finish(result)


def cmd_build(settings: Settings, args: argparse.Namespace) -> int:
    project = settings.project_path(args.tests)

    def run() -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        with repo_lock(settings, "build"):
            if not args.no_import:
                check_project_state(settings, project, args.force)
                steps.append(import_step(settings, args.tests, project))
            elif not project.exists():
                raise CdsError(f"нет проекта {project}: уберите --no-import или выполните import", EXIT_ENV)
            steps.append(build_step(settings, project))
            result = run_codesys(settings, "build.py", {"steps": steps}, "build")
            if _step(result, "import").get("ok"):
                record_project_state(settings, project, layout_subdirs(args.tests))
            return result

    result = run_with_deps(settings, run, not args.no_deps)
    annotate_build(settings, result)
    return _finish(result)


def _git_commit(repo_root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    sha = proc.stdout.strip()
    if proc.returncode != 0 or not sha:
        return None
    dirty = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"], capture_output=True, text=True, check=False
    ).stdout.strip()
    return sha + ("-dirty" if dirty else "")


def cmd_test(settings: Settings, args: argparse.Namespace) -> int:
    project = settings.project_path(True)
    results_path = settings.path("tests.results")
    junit_path = settings.path("tests.junit")
    runtime: dict[str, Any] = {}

    def run() -> dict[str, Any]:
        with repo_lock(settings, "test"), runtime_lock(settings, f"test {settings.repo_root.name}"):
            # Результаты прошлого прогона удаляются: при ошибке сборки или входа в рантайм старый
            # junit.xml с зелёными тестами иначе остался бы в build/ и ввёл бы в заблуждение CI
            for stale in (results_path, junit_path):
                with contextlib.suppress(FileNotFoundError):
                    stale.unlink()
            check_project_state(settings, project, args.force)
            runtime.clear()
            runtime.update(
                ensure_runtime(settings, restart=args.restart_runtime, allow_start=not args.no_runtime_start)
            )
            steps = [
                import_step(settings, True, project, clean=args.clean),
                build_step(settings, project),
                test_step(settings, project),
            ]
            timeout = settings.number("codesys.timeout_s") + settings.number("tests.timeout_s")
            result = run_codesys(settings, "run_tests.py", {"steps": steps}, "test", timeout_s=timeout)
            if _step(result, "import").get("ok"):
                record_project_state(settings, project, layout_subdirs(True))
            return result

    result = run_with_deps(settings, run, not args.no_deps)
    annotate_build(settings, result)
    build = _step(result, "build")
    if results_path.exists():
        data = json.loads(results_path.read_text(encoding="utf-8"))
        data["commit"] = _git_commit(settings.repo_root)
        data["build"] = {"errors": build.get("errors"), "warnings": build.get("warnings")}
        imp = _step(result, "import")
        data["import"] = {k: len(imp.get(k, [])) for k in ("created", "updated", "removed", "moved")}
        data["runtime_process"] = runtime
        data["command"] = "python tools/codesys/cds.py test"
        results_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        junit_path.parent.mkdir(parents=True, exist_ok=True)
        junit_path.write_text(results_to_junit(data), encoding="utf-8", newline="\n")
        print(f"[cds] результаты: {results_path}, JUnit: {junit_path}")
    elif _step(result, "build") and not build.get("ok"):
        print("[cds] сборка с ошибками — тесты не запускались (build/build.log)")
    return _finish(result)


def compare_trees(expected_root: Path, actual_root: Path, subdirs: Sequence[str]) -> list[str]:
    """Сравнивает файлы *.st раскладки; возвращает строки отчёта (пусто — совпадают)."""

    def files(root: Path) -> dict[str, bytes]:
        found: dict[str, bytes] = {}
        for sub in subdirs:
            base = root / sub
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.st")):
                found[path.relative_to(root).as_posix()] = path.read_bytes()
        return found

    want = files(expected_root)
    have = files(actual_root)
    report: list[str] = []
    for rel in sorted(set(want) - set(have)):
        report.append(f"только в исходниках: {rel}")
    for rel in sorted(set(have) - set(want)):
        report.append(f"только в экспорте: {rel}")
    for rel in sorted(set(want) & set(have)):
        if want[rel] == have[rel]:
            continue
        report.append(f"различается: {rel}")
        a = want[rel].decode("utf-8", "replace").splitlines(keepends=True)
        b = have[rel].decode("utf-8", "replace").splitlines(keepends=True)
        diff = list(difflib.unified_diff(a, b, f"src:{rel}", f"export:{rel}", n=1))
        report.extend("    " + line.rstrip("\n").replace("\r", "\\r") for line in diff[:60])
    return report


def cmd_roundtrip(settings: Settings, args: argparse.Namespace) -> int:
    rt_dir = settings.path("project.roundtrip_dir")
    export_dir = rt_dir / "export"
    project = rt_dir / f"{settings.value('project.name')}-roundtrip.project"

    def run() -> dict[str, Any]:
        with repo_lock(settings, "roundtrip"):
            if export_dir.exists():
                shutil.rmtree(export_dir)
            rt_dir.mkdir(parents=True, exist_ok=True)
            steps = [
                import_step(settings, True, project, clean=True, log_dir=rt_dir, name="import"),
                export_step(settings, project, export_dir, True, log_dir=rt_dir),
                import_step(settings, True, project, log_dir=rt_dir, name="import2", reopen=True),
            ]
            return run_codesys(settings, "import_sources.py", {"steps": steps}, "roundtrip")

    result = run_with_deps(settings, run, not args.no_deps)
    _print_steps(result)
    if not result.get("ok"):
        return EXIT_FAILED if result.get("exit_code") == 1 else EXIT_ENV
    report = compare_trees(settings.repo_root, export_dir, ("src", "tests"))
    second = _step(result, "import", 1)
    changes = int(second.get("changes", -1))
    if report:
        print(f"[cds] roundtrip: ДИФФ между исходниками и экспортом ({export_dir}):")
        for line in report:
            print(f"[cds]   {line}")
    else:
        n_files = len(list((export_dir / "src").rglob("*.st"))) + len(list((export_dir / "tests").rglob("*.st")))
        print(f"[cds] roundtrip: экспорт совпадает с src/ и tests/ побайтно ({n_files} файлов)")
    if changes != 0:
        print(f"[cds] roundtrip: повторный импорт изменил проект ({changes} изменений) — импорт не идемпотентен:")
        for bucket in ("created", "updated", "removed", "moved"):
            for item in second.get(bucket, []):
                print(f"[cds]   {bucket}: {item}")
    else:
        print("[cds] roundtrip: повторный импорт после открытия проекта с диска — 0 изменений")
    summary = {
        "ok": not report and changes == 0,
        "diff": report,
        "second_import_changes": changes,
        "export_dir": str(export_dir),
    }
    (rt_dir / "roundtrip.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return EXIT_OK if summary["ok"] else EXIT_FAILED


def library_summary(result: Mapping[str, Any], code: int) -> dict[str, Any]:
    """Краткий итог cds.py library для --result (его читает cds.py репозитория-потребителя)."""
    step = _step(result, "library")
    return {
        "ok": code == EXIT_OK,
        "exit_code": code,
        "library": step.get("library"),
        "compiled": step.get("compiled"),
        "installed": step.get("installed"),
        "project_info": step.get("project_info"),
        "errors": step.get("errors"),
        "warnings": step.get("warnings"),
        "error": step.get("error") or result.get("error"),
    }


def cmd_library(settings: Settings, args: argparse.Namespace) -> int:
    if args.uninstall and (args.install or args.compiled or args.released):
        raise CdsError("--uninstall не сочетается с --install, --compiled, --released", EXIT_USAGE)
    if args.all_versions and not args.uninstall:
        raise CdsError("--all-versions — только вместе с --uninstall", EXIT_USAGE)
    lib = settings.library_config()
    if args.uninstall:
        return library_uninstall(settings, lib, args.all_versions)
    step = library_step(settings, lib, args.install, args.compiled, args.released)

    def run() -> dict[str, Any]:
        with contextlib.ExitStack() as stack:
            stack.enter_context(repo_lock(settings, "library"))
            if args.install:
                stack.enter_context(library_lock(settings, f"library {lib['label']}"))
            stale = Path(lib["compiled_path"])
            if not args.compiled and stale.is_file():
                # .compiled-library прошлой сборки не соответствует новой .library (другие исходники
                # или версия) — в build/ остаются только файлы этой сборки
                stale.unlink()
                print(f"[cds] удалена {stale.name} прошлой сборки (скомпилированная библиотека — с --compiled)")
            result = run_codesys(settings, "make_library.py", {"steps": [step]}, "library")
            installed = _step(result, "library").get("installed")
            if result.get("ok") and installed:
                warning = record_install(settings, installed, _git_commit(settings.repo_root))
                if warning:
                    result["registry_warning"] = warning
            return result

    result = run_with_deps(settings, run, not args.no_deps)
    annotate_build(settings, result, "library")
    code = _finish(result)
    done = _step(result, "library")
    if done.get("ok"):
        print(f"[cds] библиотека {lib['label']}: {done.get('library')}")
        if done.get("compiled"):
            print(f"[cds] скомпилированная библиотека: {done['compiled']}")
        installed = done.get("installed")
        if installed:
            how = "заменена" if installed.get("replaced") else "установлена"
            print(
                f"[cds] {how}: {installed.get('displayname')} (пространство имён {installed.get('namespace')}) -> "
                f"репозиторий {installed.get('repository')}: {installed.get('file')}"
            )
    if result.get("registry_warning"):
        print(f"[cds] предупреждение: {result['registry_warning']}")
    if args.result:
        out = Path(args.result)
        out.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(library_summary(result, code), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        out.write_text(text, encoding="utf-8", newline="\n")
    return code


def library_uninstall(settings: Settings, lib: Mapping[str, Any], all_versions: bool) -> int:
    info = lib["info"]
    versions = [] if all_versions else [str(info["version"])]
    with library_lock(settings, f"uninstall {lib['label']}"):
        result = run_codesys(
            settings, "library_repo.py", {"steps": [uninstall_step(settings, info, versions)]}, "uninstall"
        )
        step = _step(result, "uninstall")
        if result.get("ok"):
            forget_installs(settings, step.get("removed", []))
    code = _finish(result)
    for name in step.get("removed", []):
        print(f"[cds] удалена из репозитория {step.get('repository')}: {name}")
    if step.get("ok"):
        left = ", ".join(step.get("left") or []) or "нет"
        print(f"[cds] осталось версий {info['title']} ({info['company']}): {left}")
    return code


def cmd_deps(settings: Settings, args: argparse.Namespace) -> int:
    keys = list(args.keys) or settings.referenced_library_keys()
    specs = [settings.library_spec(k) for k in keys]
    if not specs:
        print("[cds] в config.json нет библиотек-зависимостей (modes.*.libraries, library.libraries)")
        return EXIT_OK
    reinstall = [
        str(s["key"]) for s in specs if args.rebuild and s.get("install_from") and not s.get("build_from_repo")
    ]
    with library_lock(settings, "deps"):
        job = {"steps": [deps_step(settings, specs, not args.check, reinstall)]}
        result = run_codesys(settings, "library_repo.py", job, "deps")
    if not result.get("ok"):
        return _finish(result)
    entries = {str(e.get("key")): e for e in _step(result, "deps").get("libraries", [])}
    built: dict[str, dict[str, Any]] = {}
    if not args.check:
        for spec in specs:
            entry = entries.get(str(spec["key"])) or {}
            # библиотека без своих зависимостей (missing_dependencies) пересобирается: сборка в её
            # репозитории ставит и зависимости (они описаны в его config.json)
            incomplete = not entry.get("found") or entry.get("missing_dependencies")
            if spec.get("build_from_repo") and (args.rebuild or incomplete):
                built[str(spec["key"])] = build_dependency(settings, spec)
    missing: list[str] = []
    print("[cds] библиотеки-зависимости:")
    for spec in specs:
        key = str(spec["key"])
        entry = entries.get(key) or {}
        pin = spec.get("version") or C.VERSION_NEWEST
        if key in built:
            installed = built[key].get("installed") or {}
            source = spec["build_from_repo"]
            print(f"[cds]   {key} {pin}: {installed.get('displayname')} — собрана в {source} и установлена")
        elif entry.get("found"):
            how = "установлена из файла" if entry.get("installed_now") else "есть в репозитории"
            versions = ", ".join(entry.get("installed_versions") or [])
            print(f"[cds]   {key} {pin}: {entry.get('displayname')} — {how} (установлены версии: {versions})")
            for line in install_provenance(settings, spec, entry):
                print(f"[cds]     {line}")
            if entry.get("missing_dependencies"):
                print(f"[cds]     НЕТ её зависимостей: {', '.join(entry['missing_dependencies'])}")
                missing.append(key)
        else:
            have = ", ".join(entry.get("installed_versions") or []) or "нет"
            print(f"[cds]   {key} {pin}: НЕТ (установлены версии: {have})")
            missing.append(key)
    if missing:
        if args.check:
            print(
                f"[cds] нет библиотек (или их зависимостей): {', '.join(missing)} "
                "(cds.py deps без --check установит или соберёт их)"
            )
            return EXIT_FAILED
        raise CdsError(
            f"нет библиотек (или их зависимостей) {', '.join(missing)}: задайте файл .library (install_from) или "
            "репозиторий (build_from_repo) в config.json: libraries / missing libraries",
            EXIT_ENV,
        )
    return EXIT_OK


# ---------------------------------------------------------------------------
# Рантайм: пользовательский процесс CODESYS Control Win V3
# ---------------------------------------------------------------------------


def _ps_quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _powershell(script: str, timeout_s: float = 60) -> str:
    if sys.platform != "win32":
        raise CdsError("управление рантаймом — только в Windows / runtime management requires Windows", EXIT_ENV)
    full = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $ErrorActionPreference = 'Stop'; " + script
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", full],
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )
    out = proc.stdout.decode("utf-8", "replace")
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace") or proc.stderr.decode(_oem_encoding(), "replace")
        raise CdsError(f"PowerShell: {err.strip() or out.strip()}", EXIT_ENV)
    return out


def _norm(text: str) -> str:
    return os.path.normcase(text.replace("/", "\\")).replace('"', "")


def parse_processes(text: str) -> list[dict[str, Any]]:
    """Разбор ConvertTo-Json от Get-CimInstance Win32_Process (объект или массив)."""
    text = text.strip()
    if not text:
        return []
    data = json.loads(text)
    items = data if isinstance(data, list) else [data]
    result = []
    for item in items:
        created = item.get("Created")
        result.append(
            {
                "pid": int(item.get("ProcessId")),
                "cmdline": item.get("CommandLine") or "",
                "exe": item.get("ExecutablePath") or "",
                "created": created,
            }
        )
    return result


def runtime_processes() -> list[dict[str, Any]]:
    script = (
        f"$p = @(Get-CimInstance Win32_Process -Filter \"Name='{RUNTIME_IMAGE}'\" | ForEach-Object {{ "
        "[pscustomobject]@{ ProcessId = $_.ProcessId; CommandLine = $_.CommandLine; "
        "ExecutablePath = $_.ExecutablePath; "
        "Created = $_.CreationDate.ToString('o') } }); if ($p.Count -gt 0) { ConvertTo-Json -InputObject $p -Compress }"
    )
    return parse_processes(_powershell(script))


def is_our_runtime(proc: Mapping[str, Any], boot_cfg: Path) -> bool:
    """Наш процесс — с ключом -d <boot.cfg>; служба Windows и чужие экземпляры не трогаются."""
    return _norm(str(boot_cfg)) in _norm(str(proc.get("cmdline", "")))


def port_open(host: str, port: int, timeout_s: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _age_min(created: str | None) -> float | None:
    if not created:
        return None
    try:
        start = dt.datetime.fromisoformat(created)
    except ValueError:
        return None
    now = dt.datetime.now(start.tzinfo) if start.tzinfo else dt.datetime.now()
    return (now - start).total_seconds() / 60.0


def runtime_status(settings: Settings) -> dict[str, Any]:
    boot = settings.path("runtime.boot_cfg")
    port = int(settings.number("runtime.port"))
    procs = runtime_processes()
    ours = [p for p in procs if is_our_runtime(p, boot)]
    others = [p for p in procs if not is_our_runtime(p, boot)]
    status: dict[str, Any] = {
        "running": bool(ours),
        "pid": ours[0]["pid"] if ours else None,
        "started": ours[0]["created"] if ours else None,
        "age_min": round(_age_min(ours[0]["created"]) or 0, 1) if ours else None,
        "port": port,
        "port_open": port_open("127.0.0.1", port),
        "boot_cfg": str(boot),
        "other_instances": [{"pid": p["pid"], "cmdline": p["cmdline"]} for p in others],
    }
    if ours:
        status["demo_left_min"] = round(settings.number("runtime.demo_limit_min") - (status["age_min"] or 0), 1)
    return status


def runtime_init(settings: Settings) -> list[str]:
    """Каталог рантайма: boot.cfg (CRLF), work/CODESYSControl.cfg (копия штатного), credentials.json."""
    done: list[str] = []
    work = settings.path("runtime.work_dir")
    boot = settings.path("runtime.boot_cfg")
    work.mkdir(parents=True, exist_ok=True)
    if not boot.exists():
        boot.parent.mkdir(parents=True, exist_ok=True)
        work_text = str(work).rstrip("\\/") + "\\"
        boot.write_bytes(f"[SysFile]\r\nWindows.WorkingDirectory={work_text}\r\n".encode())
        done.append(f"создан {boot}")
    cfg = work / "CODESYSControl.cfg"
    if not cfg.exists():
        pattern = str(settings.path("runtime.cfg_template"))
        matches = sorted(glob.glob(pattern))
        if not matches:
            raise CdsError(
                f"не найден штатный CODESYSControl.cfg ({pattern}): установите CODESYS Control Win V3 "
                "или задайте CODESYS_RUNTIME_CFG_TEMPLATE / runtime config template not found",
                EXIT_ENV,
            )
        shutil.copyfile(matches[0], cfg)
        done.append(f"скопирован {matches[0]} -> {cfg}")
    creds = settings.path("runtime.credentials")
    if not creds.exists():
        creds.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "user": "cdsci",
            "password": secrets.token_urlsafe(18),
            "note": "Тестовый пользователь локального рантайма CODESYS Control Win (создан cds.py runtime init). "
            "Не коммитить. Первый вход на свежий рантайм создаёт этого пользователя.",
        }
        creds.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        done.append(f"создан {creds} (пароль сгенерирован, в вывод не печатается)")
    return done


def _start_hidden(exe: Path, arguments: Sequence[str], work: Path, log: Path, err: Path, marker: Path) -> int:
    """Скрытый запуск процесса через Start-Process; PID — через файл-маркер.

    Вывод PowerShell нельзя читать через канал: дочерний процесс наследует дескрипторы
    PowerShell, канал не закрывается, пока работает рантайм, и чтение зависает (проверено).
    Поэтому PowerShell запускается без каналов (DEVNULL), а PID или ошибку пишет в marker.
    """
    if sys.platform != "win32":
        raise CdsError("управление рантаймом — только в Windows / runtime management requires Windows", EXIT_ENV)
    with contextlib.suppress(FileNotFoundError):
        marker.unlink()
    args = ", ".join(_ps_quote(a) for a in arguments)
    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"try {{ $p = Start-Process -FilePath {_ps_quote(str(exe))} -ArgumentList @({args}) "
        f"-WorkingDirectory {_ps_quote(str(work))} -WindowStyle Hidden -PassThru "
        f"-RedirectStandardOutput {_ps_quote(str(log))} -RedirectStandardError {_ps_quote(str(err))}; "
        f"Set-Content -LiteralPath {_ps_quote(str(marker))} -Value ('OK ' + $p.Id) -Encoding UTF8 }} "
        f"catch {{ Set-Content -LiteralPath {_ps_quote(str(marker))} -Value ('ERR ' + $_.Exception.Message) "
        "-Encoding UTF8 }"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
        check=False,
    )
    try:
        text = marker.read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError:
        raise CdsError("Start-Process не сообщил PID рантайма / runtime start failed", EXIT_ENV) from None
    finally:
        with contextlib.suppress(FileNotFoundError):
            marker.unlink()
    if not text.startswith("OK "):
        raise CdsError(f"Start-Process: {text.removeprefix('ERR ').strip()}", EXIT_ENV)
    return int(text[3:].strip())


def runtime_start(settings: Settings) -> dict[str, Any]:
    status = runtime_status(settings)
    if status["running"]:
        return status
    if status["port_open"]:
        others = ", ".join(str(p["pid"]) for p in status["other_instances"]) or "?"
        raise CdsError(
            f"порт {status['port']} занят другим процессом (PID {others}; служба CODESYS Control Win V3?). "
            "Остановите его сами или используйте его без cds.py runtime / port is busy",
            EXIT_ENV,
        )
    for line in runtime_init(settings):
        print(f"[cds] {line}")
    exe = settings.path("runtime.exe", must_exist=True)
    boot = settings.path("runtime.boot_cfg")
    work = settings.path("runtime.work_dir")
    log = settings.path("runtime.log_file")
    err = log.with_suffix(".err")
    pid_file = settings.path("runtime.pid_file")
    pid = _start_hidden(exe, ["-d", f'"{boot}"'], work, log, err, pid_file.with_suffix(".start"))
    pid_file.write_text(
        json.dumps({"pid": pid, "started": dt.datetime.now().isoformat(timespec="seconds"), "boot_cfg": str(boot)})
        + "\n",
        encoding="utf-8",
    )
    deadline = time.monotonic() + settings.number("runtime.start_timeout_s")
    port = int(settings.number("runtime.port"))
    while time.monotonic() < deadline:
        if port_open("127.0.0.1", port):
            break
        if not any(p["pid"] == pid for p in runtime_processes()):
            raise CdsError(f"рантайм (PID {pid}) завершился при старте; журнал: {log}, {err}", EXIT_ENV)
        time.sleep(1.0)
    else:
        raise CdsError(f"рантайм (PID {pid}) не открыл порт {port} за отведённое время; журнал: {log}", EXIT_TIMEOUT)
    return runtime_status(settings)


def runtime_stop(settings: Settings) -> list[int]:
    boot = settings.path("runtime.boot_cfg")
    stopped = []
    for proc in runtime_processes():
        if not is_our_runtime(proc, boot):
            continue
        _powershell(f"Stop-Process -Id {int(proc['pid'])} -Force")
        stopped.append(int(proc["pid"]))
    deadline = time.monotonic() + 30
    while stopped and time.monotonic() < deadline:
        alive = {p["pid"] for p in runtime_processes()}
        if not alive & set(stopped):
            break
        time.sleep(0.5)
    with contextlib.suppress(FileNotFoundError):
        settings.path("runtime.pid_file").unlink()
    return stopped


def ensure_runtime(settings: Settings, restart: bool = False, allow_start: bool = True) -> dict[str, Any]:
    """Рантайм для тестов: запуск при отсутствии, перезапуск перед истечением демо-режима (2 ч)."""
    status = runtime_status(settings)
    max_age = settings.number("runtime.restart_after_min")
    if status["running"] and (restart or (status["age_min"] or 0) >= max_age):
        reason = "--restart-runtime" if restart else f"работает {status['age_min']} мин, демо-режим — 2 ч"
        print(f"[cds] перезапуск рантайма ({reason})")
        runtime_stop(settings)
        status = runtime_status(settings)
    if status["running"]:
        print(f"[cds] рантайм: PID {status['pid']}, работает {status['age_min']} мин")
        return status
    if status["port_open"]:
        print(
            f"[cds] рантайм: порт {status['port']} открыт сторонним экземпляром — используется он "
            "(демо-лимит не контролируется)"
        )
        return status
    if not allow_start:
        raise CdsError("рантайм не запущен: cds.py runtime start / runtime is not running", EXIT_ENV)
    print("[cds] запуск рантайма ...")
    status = runtime_start(settings)
    print(f"[cds] рантайм запущен: PID {status['pid']}")
    return status


def cmd_runtime(settings: Settings, args: argparse.Namespace) -> int:
    action = args.action
    if action == "status":
        status = runtime_status(settings)
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return EXIT_OK if status["running"] or status["port_open"] else EXIT_FAILED
    if action == "init":
        done = runtime_init(settings)
        for line in done or ["каталог рантайма уже подготовлен"]:
            print(f"[cds] {line}")
        return EXIT_OK
    with runtime_lock(settings, f"runtime {action}"):
        if action in ("stop", "restart"):
            stopped = runtime_stop(settings)
            print(f"[cds] остановлено: {stopped or 'нечего останавливать'}")
            if action == "stop":
                return EXIT_OK
        status = runtime_start(settings)
        print(json.dumps(status, indent=2, ensure_ascii=False))
    return EXIT_OK


# ---------------------------------------------------------------------------
# JUnit и отчёт
# ---------------------------------------------------------------------------


def results_to_junit(results: Mapping[str, Any]) -> str:
    """JUnit XML из build/test-results.json (формат, который понимают CI и IDE)."""
    totals = results.get("totals") or {}
    root = ET.Element(
        "testsuites",
        {
            "name": str(results.get("framework") or "coUnit"),
            "tests": str(totals.get("tests", 0)),
            "failures": str(totals.get("failed", 0)),
            "skipped": str(totals.get("skipped", 0)),
            "errors": "0" if results.get("finished") else "1",
        },
    )
    if not results.get("finished"):
        err_suite = ET.SubElement(root, "testsuite", {"name": "coUnit", "tests": "1", "failures": "0", "errors": "1"})
        case = ET.SubElement(err_suite, "testcase", {"name": "AllTestSuitesFinished", "classname": "coUnit"})
        ET.SubElement(case, "error", {"message": str(results.get("error") or "прогон не завершён (таймаут)")})
    for suite in results.get("suites", []):
        attrs = {
            "name": str(suite.get("name")),
            "tests": str(suite.get("tests", 0)),
            "failures": str(suite.get("failed", 0)),
            "skipped": str(suite.get("skipped", 0)),
            "errors": "0",
        }
        if results.get("started"):
            attrs["timestamp"] = str(results["started"])
        node = ET.SubElement(root, "testsuite", attrs)
        for case in suite.get("cases", []):
            tc = ET.SubElement(
                node,
                "testcase",
                {"name": str(case.get("name")), "classname": str(case.get("class_name") or suite.get("name"))},
            )
            if case.get("status") == "FAIL":
                failure = ET.SubElement(
                    tc,
                    "failure",
                    {"message": str(case.get("message") or ""), "type": str(case.get("failure_type") or "")},
                )
                failure.text = str(case.get("message") or "")
            elif case.get("status") == "SKIP":
                ET.SubElement(tc, "skipped")
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def _status_ru(status: str) -> str:
    return {"PASS": "пройден", "FAIL": "**упал**", "SKIP": "пропущен"}.get(status, status)


def render_report(results: Mapping[str, Any]) -> str:
    """Раздел docs/TEST_REPORT.md с итогами последнего прогона (между маркерами)."""
    totals = results.get("totals") or {}
    started = str(results.get("started") or "").replace("T", " ")
    finished = bool(results.get("finished"))
    failed = int(totals.get("failed") or 0)
    ok = finished and failed == 0 and int(totals.get("tests") or 0) > 0
    build = results.get("build") or {}
    lines = [
        REPORT_BEGIN,
        "## Последний прогон в CODESYS",
        "",
        f"Проверено в CODESYS {results.get('codesys_version', '?')} / "
        f"{results.get('runtime', 'CODESYS Control Win V3')}"
        f" — {started}. Итог: **{'все тесты пройдены' if ok else 'есть ошибки'}**.",
        "",
        "| Параметр | Значение |",
        "|---|---|",
        f"| Дата прогона | {_cell(started)} |",
        f"| Коммит | {_cell(results.get('commit') or '— (нет коммита)')} |",
        f"| CODESYS | {_cell(results.get('codesys_version'))} (профиль `{_cell(results.get('profile'))}`) |",
        f"| Устройство в проекте | {_cell(results.get('device'))} |",
        f"| Рантайм | {_cell(results.get('runtime'))} |",
        f"| Фреймворк тестов | {_cell(results.get('framework'))} |",
        f"| Сборка | ошибок {_cell(build.get('errors'))}, предупреждений {_cell(build.get('warnings'))} |",
        f"| Способ запуска | `{_cell(results.get('command') or 'python tools/codesys/cds.py test')}` |",
        "",
        "| Набор | Тестов | Пройдено | Упало | Пропущено | Итог |",
        "|---|---|---|---|---|---|",
    ]
    for suite in results.get("suites", []):
        s_failed = int(suite.get("failed") or 0)
        s_skipped = int(suite.get("skipped") or 0)
        s_tests = int(suite.get("tests") or 0)
        verdict = "пройдено" if s_failed == 0 and s_tests > 0 else "**упало**"
        lines.append(
            f"| `{_cell(suite.get('name'))}` | {s_tests} | {s_tests - s_failed - s_skipped} | {s_failed} | "
            f"{s_skipped} | {verdict} |"
        )
    lines.append(
        f"| **Всего** | {totals.get('tests', 0)} | {totals.get('passed', 0)} | {totals.get('failed', 0)} | "
        f"{totals.get('skipped', 0)} | **{'пройдено' if ok else 'не пройдено'}** |"
    )
    if not finished:
        lines += ["", f"Прогон не завершён: {_cell(results.get('error') or 'таймаут ожидания AllTestSuitesFinished')}."]
    lines += ["", "### Результаты тестов", "", "| Набор | Тест | Итог |", "|---|---|---|"]
    for suite in results.get("suites", []):
        for case in suite.get("cases", []):
            status = _status_ru(str(case.get("status")))
            lines.append(f"| `{_cell(suite.get('name'))}` | `{_cell(case.get('name'))}` | {status} |")
    lines += ["", "### Упавшие тесты", ""]
    failures = [(s, c) for s in results.get("suites", []) for c in s.get("cases", []) if c.get("status") == "FAIL"]
    if failures:
        lines += ["| Набор | Тест | Сообщение coUnit | Тип проверки |", "|---|---|---|---|"]
        for suite, case in failures:
            lines.append(
                f"| `{_cell(suite.get('name'))}` | `{_cell(case.get('name'))}` | {_cell(case.get('message'))} | "
                f"{_cell(case.get('failure_type'))} |"
            )
    else:
        lines.append("_Нет._")
    lines += ["", "Машиночитаемые результаты: `build/test-results.json`, `build/junit.xml` (не в git).", REPORT_END]
    return "\n".join(lines) + "\n"


def update_report(doc: str, section: str) -> str:
    """Заменяет раздел между маркерами; без маркеров — вставляет перед первым заголовком '## '."""
    begin = doc.find(REPORT_BEGIN.split(" (")[0])
    end = doc.find(REPORT_END)
    if begin >= 0 and end > begin:
        tail = doc[end + len(REPORT_END) :]
        if tail.startswith("\n"):
            tail = tail[1:]
        return doc[:begin] + section + tail
    match = re.search(r"^## ", doc, re.MULTILINE)
    if match is None:
        return doc.rstrip("\n") + "\n\n" + section
    return doc[: match.start()] + section + "\n" + doc[match.start() :]


def _load_results(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CdsError(f"нет файла результатов {path}: сначала cds.py test / no results file", EXIT_ENV) from None
    if not isinstance(data, dict):
        raise CdsError(f"{path}: ожидался объект JSON", EXIT_USAGE)
    return data


def cmd_junit(settings: Settings, args: argparse.Namespace) -> int:
    results_path = Path(args.results) if args.results else settings.path("tests.results")
    out = Path(args.out) if args.out else settings.path("tests.junit")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(results_to_junit(_load_results(results_path)), encoding="utf-8", newline="\n")
    print(f"[cds] JUnit: {out}")
    return EXIT_OK


def cmd_report(settings: Settings, args: argparse.Namespace) -> int:
    results_path = Path(args.results) if args.results else settings.path("tests.results")
    doc_path = Path(args.doc) if args.doc else settings.path("tests.report_doc")
    results = _load_results(results_path)
    doc = doc_path.read_text(encoding="utf-8") if doc_path.exists() else "# Отчёт о тестировании\n"
    new = update_report(doc, render_report(results))
    doc_path.write_text(new, encoding="utf-8", newline="\n")
    print(f"[cds] обновлён раздел «Последний прогон в CODESYS» в {doc_path}")
    return EXIT_OK


# ---------------------------------------------------------------------------
# Разбор аргументов
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cds.py",
        description="Импорт, сборка, тесты, экспорт и библиотеки CODESYS 3.5 из консоли (docs/MANUAL_STEPS.md).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    no_deps_help = "не собирать недостающие библиотеки в соседних репозиториях (libraries.*.build_from_repo)"

    p = sub.add_parser("import", help="исходники src/ (и tests/) -> проект CODESYS")
    p.add_argument("--tests", action="store_true", help="с tests/ в тестовый проект (режим test)")
    p.add_argument("--clean", action="store_true", help="пересоздать проект с нуля")
    p.add_argument("--force", action="store_true", help="перезаписать проект, даже если он сохранён в IDE")
    p.add_argument("--no-deps", action="store_true", help=no_deps_help)
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("export", help="проект CODESYS -> раскладка src/ (и tests/)")
    p.add_argument("--tests", action="store_true", help="экспорт тестового проекта, включая tests/")
    p.add_argument("--to", metavar="DIR", help="каталог вместо корня репозитория (пишутся DIR/src, DIR/tests)")
    p.add_argument("--force", action="store_true", help="перезаписать src/, даже если исходники менялись после импорта")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("build", help="импорт и сборка (build/build.log, build/build.json)")
    p.add_argument("--tests", action="store_true", help="собрать тестовый проект")
    p.add_argument("--no-import", action="store_true", help="собрать проект как есть, без импорта")
    p.add_argument("--force", action="store_true", help="импортировать, даже если проект сохранён в IDE")
    p.add_argument("--no-deps", action="store_true", help=no_deps_help)
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("test", help="импорт с тестами, сборка, прогон coUnit в рантайме")
    p.add_argument("--restart-runtime", action="store_true", help="перезапустить рантайм перед прогоном")
    p.add_argument("--no-runtime-start", action="store_true", help="не запускать рантайм автоматически")
    p.add_argument("--clean", action="store_true", help="пересоздать тестовый проект с нуля")
    p.add_argument("--force", action="store_true", help="импортировать, даже если проект сохранён в IDE")
    p.add_argument("--no-deps", action="store_true", help=no_deps_help)
    p.set_defaults(func=cmd_test)

    p = sub.add_parser("roundtrip", help="импорт -> экспорт во временный каталог -> сравнение с src/ и tests/")
    p.add_argument("--no-deps", action="store_true", help=no_deps_help)
    p.set_defaults(func=cmd_roundtrip)

    p = sub.add_parser(
        "library",
        help="src/ -> библиотека build/<имя>.library (Project Information — config.json: library), установка",
    )
    p.add_argument("--install", action="store_true", help="установить в репозиторий библиотек (library_repository)")
    p.add_argument("--compiled", action="store_true", help="также .compiled-library; с --install ставится она")
    p.add_argument("--released", action="store_true", help="отметить в Project Information как выпущенную (released)")
    p.add_argument("--uninstall", action="store_true", help="удалить версию library.version из репозитория библиотек")
    p.add_argument("--all-versions", action="store_true", help="с --uninstall: удалить все версии этой библиотеки")
    p.add_argument("--no-deps", action="store_true", help=no_deps_help)
    p.add_argument("--result", metavar="FILE", help="итог в JSON (его читает cds.py репозитория-потребителя)")
    p.set_defaults(func=cmd_library)

    p = sub.add_parser("deps", help="библиотеки из config.json: проверка, установка, сборка в соседних репозиториях")
    p.add_argument("keys", nargs="*", metavar="KEY", help="ключи libraries (по умолчанию — все, на которые ссылаются)")
    p.add_argument("--rebuild", action="store_true", help="пересобрать и переустановить, даже если версия уже есть")
    p.add_argument("--check", action="store_true", help="только проверить (код 1, если чего-то нет)")
    p.set_defaults(func=cmd_deps)

    p = sub.add_parser("runtime", help="пользовательский процесс CODESYS Control Win V3")
    p.add_argument("action", choices=("start", "stop", "status", "restart", "init"))
    p.set_defaults(func=cmd_runtime)

    p = sub.add_parser("junit", help="build/test-results.json -> build/junit.xml")
    p.add_argument("--results", metavar="FILE")
    p.add_argument("--out", metavar="FILE")
    p.set_defaults(func=cmd_junit)

    p = sub.add_parser("report", help="обновить раздел последнего прогона в docs/TEST_REPORT.md")
    p.add_argument("--results", metavar="FILE")
    p.add_argument("--doc", metavar="FILE")
    p.set_defaults(func=cmd_report)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(Exception):
                reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        settings = make_settings()
        code: int = args.func(settings, args)
        return code
    except CdsError as exc:
        print(f"[cds] ОШИБКА: {exc}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("[cds] прервано", file=sys.stderr)
        return EXIT_FAILED
