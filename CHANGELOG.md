# Changelog

Все заметные изменения проекта записываются в этот файл.

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии — по
[Semantic Versioning](https://semver.org/lang/ru/spec/v2.0.0.html).

## [Unreleased]

### Added

- Раскладка исходников ST в `src/` и `tests/` и её формальный контракт `docs/LAYOUT.md`.
- Пример: `E_DeviceMode`, `ST_ExampleCmd`, `ST_ExampleSts`, `GVL_Const`, интерфейс `I_Resettable`,
  функция `F_Clamp`, `FB_Example` (метод `Acknowledge`, реализация `Reset`, свойство `Count`), `PRG_Main`.
- Тесты CfUnit (coUnit 1.2.0.0): наборы `FB_F_Clamp_Test` (7 тестов), `FB_Example_Test` (11 тестов:
  пороги и гистерезис, отказ и квитирование, режимы, ограничение параметров, счётчик, сброс через
  `I_Resettable`) и `PRG_Tests`.
- Инструменты: `tools/assemble.py`, `tools/check/` (линтер `st_lint.py`, запуск iec_checker и RuSTy),
  скрипты CODESYS Scripting в `tools/codesys/`.
- `tools/codesys/cds.py` — импорт, сборка, тесты coUnit в CODESYS Control Win V3 (пользовательский
  процесс), экспорт, roundtrip, JUnit и отчёт из консоли; настройки — `tools/codesys/config.json`.
  Проверено в CODESYS 3.5.17.30.
- `cds.py library [--install] [--compiled] [--released]`: библиотека CODESYS из `src/` — `build/<имя>.library`
  (и `.compiled-library`) с Project Information из `config.json: library`, «проверить все объекты пула»
  с ошибками в строках `src/`, установка в репозиторий библиотек; `library --uninstall [--all-versions]`.
  Проверено в CODESYS 3.5.17.30.
- Библиотеки-зависимости портфолио: в `config.json: libraries` — закрепление версии (точная или `*`),
  пространство имён ссылки, плейсхолдер, `install_from` и `build_from_repo`; `cds.py deps [--rebuild]
  [--check]`; `import`/`build`/`test` сами собирают недостающую библиотеку в соседнем репозитории
  (`cds.py library --install` там) и повторяют задание (`--no-deps` — отключить). Найденная библиотека
  проверяется и по её собственным зависимостям (рекурсивно); цикл зависимостей между репозиториями —
  отказ, а не бесконечная цепочка сборок. Ссылки `library.libraries` подключаются и к проектам
  приложения и тестов репозитория-библиотеки. Учёт установок: из какой рабочей копии и коммита
  поставлена версия.
- Разделы `library` и `library_repository` в `tools/codesys/config.json`, глобальная блокировка
  репозитория библиотек; тесты `tools/tests/test_cds_library.py`.
- CI GitHub Actions: ruff, mypy, pytest, сборка ST, линтер (`--strict`), iec_checker v0.4 (закреплён
  по размеру и SHA-256); необязательно — iec_checker `nightly` (образ закреплён по дайджесту) и RuSTy.
- Документы: архитектура, ручные шаги, допущения, отчёты статанализа и тестов, шаблоны ТЗ
  (ГОСТ 34.602-2020) и ПМИ.
- `LICENSE` (MIT), `.gitignore`, `.gitattributes`, `.editorconfig`.

### Fixed

- Тесты coUnit: функции `TEST` и `TEST_FINISHED` вызываются с пространством имён (`coUnit.TEST(...)`) —
  без него сборка в CODESYS 3.5.17.30 давала ошибки C0046/C0035.
- `cds.py build`/`test`: перед открытием проекта удаляется кэш предкомпиляции CODESYS — с ним
  сломанное объявление ФБ с методами собиралось с «0 ошибок», а исправленное давало старую ошибку.
- `cds.py`: устаревший файл блокировки `<проект>.~u` (CODESYS остановлен по таймауту или упал)
  удаляется, проект, открытый в IDE, — понятный отказ с кодом 3 вместо трассировки.
- `cds.py import`: переименование только регистром (файл, метод, свойство, папка) доходит до проекта.
- `cds.py test`: старые `build/junit.xml` и `build/test-results.json` удаляются перед прогоном;
  неудачный вход в рантайм — одна строка с причиной и код 3 вместо трассировки; имя пользователя
  рантайма не пишется в журнал.
- `docs/MANUAL_STEPS.md`, `README.md`: команды без `& rem` — работают в cmd, PowerShell и Git Bash.
- `cds.py import`: ссылка на библиотеку другой версии заменяется (раньше оставалась старая, и в проекте
  оказывались обе); новейшая версия выбирается по номеру, а не по строке (`1.10` новее `1.9`); все
  недостающие библиотеки — в одном сообщении, до изменения проекта.
- `cds.py`: переменные рабочей копии (`CDS_REPO_ROOT`, `CDS_CONFIG`, `CDS_PROJECT*`, `CDS_LIBRARY*`) не
  читаются из `HKCU\Environment` — заданные через `setx`, они действовали бы на все git worktree сразу.
- Кэш предкомпиляции: имя по расширению файла (`<имя>_library.precompilecache` у библиотеки) — сборка
  библиотеки больше не удаляет кэш проекта `<имя>_project.precompilecache`.
