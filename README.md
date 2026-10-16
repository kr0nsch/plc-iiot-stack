# plc-iiot-stack

[![CI](https://github.com/<GITHUB_USER>/plc-iiot-stack/actions/workflows/ci.yml/badge.svg)](https://github.com/<GITHUB_USER>/plc-iiot-stack/actions/workflows/ci.yml)

Шаблон репозитория для ПЛК-проектов на CODESYS V3.5 (3.5.17.30, целевой ПЛК — ОВЕН ПЛК210).
Решает главную проблему ПЛК-кода в git: проект CODESYS (`.project`) бинарный, его нельзя ревьюить
и сливать. Здесь источник истины — текстовые файлы ST, проект собирается из них скриптом, а
проверки (линтер, статанализ, проверка компиляции) идут в CI без CODESYS.

## Демонстрация

> _Плейсхолдер: GIF «импорт → сборка → тесты CfUnit в Control Win» появится после первого
> прогона в CODESYS._

## Архитектура

```mermaid
flowchart LR
    src["src/, tests/<br/>тексты ST"] --> lint["st_lint"]
    src --> asm["assemble.py"] --> built["build/assembled/"]
    built --> iec["iec_checker"]
    built --> rusty["RuSTy --check"]
    src --> imp["cds.py import"] --> proj["проект CODESYS"]
    proj --> bld["cds.py build"] --> tst["cds.py test<br/>Control Win + coUnit"] --> rep["TEST_REPORT.md"]
    proj -- "правки в IDE" --> exp["cds.py export"] --> src
```

Подробно — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Почему такая раскладка

- **Один объект CODESYS — один файл или папка** (`src/POUs/FB_Example/FB_Example.decl.st`,
  `Reset.method.impl.st`, `Count.get.impl.st`...). Дифф в pull request показывает, какой метод
  изменился, а не «изменился бинарный файл».
- **Объявление и тело — разные файлы**, как в редакторе CODESYS: импорт и экспорт однозначны,
  и цикл «импорт → экспорт» без правок не должен давать диффа (критерий проверки скриптов).
- **Склейка в стандартный ST** (`tools/assemble.py`) позволяет проверять код открытыми
  инструментами — iec_checker и RuSTy — без лицензии и без Windows.
- Контракт раскладки — [docs/LAYOUT.md](docs/LAYOUT.md), правила кода — [CONTRIBUTING.md](CONTRIBUTING.md).

## Быстрый старт без железа

Нужен Python 3.11+ (в CI — 3.12). CODESYS не нужен.

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt

python -m pytest                       # тесты инструментов
python tools/check/st_lint.py --strict # правила CONTRIBUTING.md: заголовки, имена, «магические числа»
python tools/assemble.py --tests       # стандартный ST в build/assembled/

# статанализ: бинарник iec_checker v0.4 из релизов (--binary <путь> или переменная IEC_CHECKER)
# или Docker-образ (--docker jubnzv1/iec-checker:nightly)
python tools/check/run_iec_checker.py --binary <путь к iec_checker> --tests
# необязательно: проверка компиляции RuSTy (бинарник plc и stdlib из релиза PLC-lang/rusty v1.0.6)
python tools/check/run_rusty.py --plc <путь к plc> --stdlib <stdlib/include>
```

Отчёты — в `build/` (`iec_checker.md`, `rusty.log`). Опции инструментов — в
[tools/README.md](tools/README.md).

## CODESYS: импорт, сборка, тесты, экспорт

Нужны Windows, CODESYS 3.5.17.30 и Python 3.11+. Всё делает одна команда `tools/codesys/cds.py`:
она запускает CODESYS без окна (`--noUI`) со скриптами CODESYS Scripting, а тесты coUnit — в
CODESYS Control Win V3, запущенном пользовательским процессом (без прав администратора).

| Команда (из корня репозитория; cmd, PowerShell или Git Bash) | Что делает |
|---|---|
| `python tools/codesys/cds.py import` | `src/` → `build/<имя>.project` |
| `python tools/codesys/cds.py build` | импорт и сборка; ошибки — с файлом и строкой в `src/` |
| `python tools/codesys/cds.py test` | `src/` + `tests/` → сборка → прогон в рантайме → `build/test-results.json`, `build/junit.xml` |
| `python tools/codesys/cds.py roundtrip` | импорт → экспорт → побайтное сравнение с `src/` и `tests/` |
| `python tools/codesys/cds.py export` | после правок в IDE: проект → `src/` (до коммита) |
| `python tools/codesys/cds.py report` | итоги прогона → `docs/TEST_REPORT.md` |
| `python tools/codesys/cds.py library --install` | `src/` → библиотека `build/<имя>.library` и установка в репозиторий библиотек |
| `python tools/codesys/cds.py deps` | библиотеки-зависимости: проверка, установка, сборка в соседних репозиториях |
| `python tools/codesys/cds.py runtime status` | рантайм; также `start`, `stop`, `restart`, `init` |

Путь к CODESYS и профиль — переменные `CODESYS_EXE`, `CODESYS_PROFILE` (без них — стандартный путь
установки 3.5.17.30); настройки проекта, устройства, задач и библиотек — `tools/codesys/config.json`.
Проверено в CODESYS 3.5.17.30 / CODESYS Control Win V3 (пользовательский процесс): сборка без ошибок
и предупреждений, тесты coUnit зелёные, цикл «импорт → экспорт» без диффа — см.
[docs/TEST_REPORT.md](docs/TEST_REPORT.md). Установка и первый запуск —
[docs/MANUAL_STEPS.md](docs/MANUAL_STEPS.md), все опции и переменные —
[tools/README.md](tools/README.md#codesyscdspy--codesys-из-консоли). Правило: правили в IDE —
`cds.py export` в `src/` до коммита.

## Как создать проект из шаблона

1. На GitHub: **Use this template → Create a new repository**.
2. Заменить плейсхолдеры `<ИМЯ ФАМИЛИЯ>` и `<GITHUB_USER>` (LICENSE, README, CONTRIBUTING.md, заголовки ST):
   `git grep -n -e "<ИМЯ ФАМИЛИЯ>" -e "<GITHUB_USER>"`.
3. Удалить пример (`FB_Example`, `ST_Example*`, константы `EXAMPLE_*`) или переименовать под задачу.
4. Обновить `CHANGELOG.md`, `docs/ASSUMPTIONS.md` и `tools/codesys/config.json` (для библиотеки —
   раздел `library`: название, компания, версия, пространство имён).

## Зеркало на GitVerse или GitFlic

```bash
git remote add mirror <url>
git push mirror --all
git push mirror --tags
```

## Тесты и проверки

| Проверка | Где | Что |
|---|---|---|
| ruff, mypy, pytest | CI | код инструментов на Python |
| `st_lint --strict` | CI | раскладка, заголовки POU, табы, длина строки, `TODO` без issue, «магические числа» |
| iec_checker | CI: v0.4 (как локально) — обязательно; образ `nightly` — необязательно | статанализ; находки — в [docs/STATIC_ANALYSIS.md](docs/STATIC_ANALYSIS.md) |
| RuSTy `plc --check` | CI, необязательно | синтаксис и типы собранного ST |
| сборка CODESYS 3.5.17.30 | Windows с CODESYS: `cds.py build` | ошибки и предупреждения компилятора — `build/build.log` |
| CfUnit (coUnit 1.2.0.0) | Windows с CODESYS: `cds.py test` (Control Win V3) | юнит-тесты ST; итоги — в [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |
| roundtrip | Windows с CODESYS: `cds.py roundtrip` | «импорт → экспорт» без диффа, повторный импорт без изменений |

## Документация

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — схема работы и пример в `src/`
- [LAYOUT.md](docs/LAYOUT.md) — контракт раскладки исходников
- [MANUAL_STEPS.md](docs/MANUAL_STEPS.md) — шаги в IDE CODESYS
- [ASSUMPTIONS.md](docs/ASSUMPTIONS.md) — допущения и решения
- [STATIC_ANALYSIS.md](docs/STATIC_ANALYSIS.md), [TEST_REPORT.md](docs/TEST_REPORT.md),
  [BUILD_ERRORS.md](docs/BUILD_ERRORS.md) — отчёты
- [TZ_template.md](docs/TZ_template.md) (ГОСТ 34.602-2020), [PMI_template.md](docs/PMI_template.md) — шаблоны ТЗ и ПМИ

## Ограничения и дальнейшие шаги

- Сборка и тесты в CODESYS выполняются только на Windows с установленным CODESYS (не в CI GitHub):
  перед релизом — `cds.py test` и `cds.py report`.
- В раскладку не входят визуализации, дерево устройств, конфигураторы обмена, графические языки,
  `ACTION`, а Persistent Variables скриптом SP17 не создаются — это ручные шаги
  ([MANUAL_STEPS.md](docs/MANUAL_STEPS.md#6-работа-в-ide-и-экспорт-перед-коммитом)).
- iec_checker и RuSTy понимают не все расширения CODESYS: для них есть упрощённые варианты сборки,
  семантика которых может отличаться.
- Тесты — на CfUnit 1.2.0.0 (пространство имён `coUnit`); фреймворк не развивается с 2022 года.

## Summary (EN)

A template repository for CODESYS V3.5 (3.5.17.30) PLC projects targeting OWEN PLC210.
The binary `.project` file is not stored in git: plain-text Structured Text files in `src/` and
`tests/` (one CODESYS object per file or folder, see `docs/LAYOUT.md`) are the source of truth.
A single command, `python tools/codesys/cds.py import|build|test|export|roundtrip`, drives headless
CODESYS Scripting (IronPython) to build the project from the sources and export IDE edits back.
`tools/assemble.py` merges the sources into standard IEC 61131-3 ST, so CI on Linux can run a
linter, the iec_checker static analyser and the RuSTy compiler without a CODESYS licence.
CfUnit (coUnit 1.2.0.0) unit tests run in a user-mode CODESYS Control Win V3 runtime. Docs are in Russian.

## Лицензия

[MIT](LICENSE) © 2026 <ИМЯ ФАМИЛИЯ>
