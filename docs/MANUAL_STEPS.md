# Ручные шаги

Шаги, которые выполняет человек в консоли Windows и в IDE CODESYS. Всё, что можно выполнить без
CODESYS (сборка текстов, линтер, статанализ), описано в [README](../README.md#быстрый-старт)
и выполняется в CI.

Команды разделов 3–7 проверены прогоном на CODESYS V3.5 SP17 Patch 3 (3.5.17.30, 32-битная сборка
ОВЕН) и CODESYS Control Win V3 в пользовательском процессе (16.10.2026), включая сборку, установку
и удаление библиотек и сборку зависимостей из соседних репозиториев. Что не проверено — отмечено
явно. Подробности об инструменте — [tools/README.md](../tools/README.md#codesyscdspy--codesys-из-консоли).
Разделы 9–12 — ПЛК-часть IIoT-стека: библиотека MQTT, символьная конфигурация для OPC UA,
встраивание во флагман и стенд против флагмана в CODESYS; что в них проверено, а что нет, тоже отмечено.

## 1. Установка CODESYS 3.5.17.30

1. Скачать CODESYS V3.5 SP17 Patch 3 (3.5.17.30) с сайта ОВЕН (раздел ПО для ПЛК2xx) и установить
   с компонентами CODESYS Control Win V3 и Gateway. Сборка ОВЕН 32-битная и ставится в
   `C:\Program Files (x86)\CODESYS 3.5.17.30\` — этот путь `cds.py` находит сам.
2. Для рабочего ПЛК — пакет таргет-файлов ОВЕН ПЛК210: «Инструменты → Установщик пакетов»
   (Tools → Package Manager). Версию таргет-файла сверить с прошивкой ПЛК. Для тестов он не нужен:
   тестовый проект собирается под CODESYS Control Win V3.
3. Имя профиля — по файлу в каталоге профилей (для 3.5.17.30 — `CODESYS V3.5 SP17 Patch 3`):

   ```bat
   dir "C:\Program Files (x86)\CODESYS 3.5.17.30\CODESYS\Profiles"
   ```

   `CODESYS.exe --help` и запуск без `--profile` открывают окно IDE (диалог выбора профиля), а не
   выводят справку в консоль — для проверки их не используйте.
4. Нужен Python 3.11+ (`python --version`), сторонние пакеты для `cds.py` не нужны.

## 2. coUnit (CfUnit) 1.2.0.0

В версии 1.2.0.0 CfUnit называется co♻e / coUnit, пространство имён в коде — `coUnit`
(см. [ASSUMPTIONS.md](ASSUMPTIONS.md), C6). Лицензия MIT.

1. Скачать `counit.library` из SVN проекта counit на CODESYS Forge (`tags/v1.2.0.0/`) обычным
   `GET` (браузером: запрос `HEAD` даёт 401).
2. Установить одним из способов:
   - в IDE: «Инструменты → Репозиторий библиотек → Установить» (Tools → Library Repository → Install);
   - или автоматически: задать путь к файлу в `COUNIT_LIBRARY` (раздел 3) — первый
     `cds.py import --tests`, не найдя coUnit 1.2.0.0 в репозиториях, установит её в репозиторий
     `System` (`librarymanager.install_library`). _Для coUnit ветка установки на этой машине не
     выполнялась: библиотека уже была установлена. Поиск по названию и версии проверен, установка
     из файла — на другой библиотеке (`cds.py deps`, тот же код)._
3. Параметры библиотеки менять не нужно: с параметрами по умолчанию тестовое приложение под
   Control Win собирается без ошибок (проверено, C7). Для ПЛК210 с меньшей памятью — сверить при
   переносе тестов на контроллер.

## 3. Переменные окружения

Абсолютных путей пользователя в репозитории нет: `cds.py` берёт их из переменных окружения, а без
них — из значений по умолчанию в `tools/codesys/config.json`. Обычно достаточно двух:

| Переменная | Значение | По умолчанию |
|---|---|---|
| `CODESYS_EXE` | полный путь к `CODESYS.exe` | `%ProgramFiles(x86)%\CODESYS 3.5.17.30\CODESYS\Common\CODESYS.exe`, затем `%ProgramFiles%\...` |
| `CODESYS_PROFILE` | имя профиля | `CODESYS V3.5 SP17 Patch 3` |
| `COUNIT_LIBRARY` | путь к `counit.library` (только если coUnit ещё не установлена) | — |
| `CODESYS_RUNTIME_CREDENTIALS` | файл с логином и паролем тестового пользователя рантайма | `%USERPROFILE%\.local\plc-tools\cds-runtime\credentials.json` |

Остальные (устройство, пути рантайма, таймауты, блокировка) — в
[tools/README.md](../tools/README.md#переменные-окружения). Задать для пользователя:

```bat
setx CODESYS_EXE "C:\Program Files (x86)\CODESYS 3.5.17.30\CODESYS\Common\CODESYS.exe"
setx CODESYS_PROFILE "CODESYS V3.5 SP17 Patch 3"
```

`setx` не меняет окружение уже открытых консолей; `cds.py` дочитывает переменные пользователя из
реестра (`HKCU\Environment`), поэтому перезапуск консоли не обязателен.

## 4. Рантайм CODESYS Control Win V3 без прав администратора

Служба Windows «CODESYS Control Win V3» требует прав администратора — её не используем. Тесты идут
в пользовательском процессе `CODESYSControlService.exe`, которым управляет `cds.py`. Команды
одинаково работают в cmd, PowerShell и Git Bash (из корня репозитория):

| Команда | Что делает |
|---|---|
| `python tools/codesys/cds.py runtime init` | один раз: каталог, `boot.cfg`, копия `CODESYSControl.cfg`, `credentials.json` |
| `python tools/codesys/cds.py runtime start` | скрытый запуск, ждёт порт 11740 |
| `python tools/codesys/cds.py runtime status` | PID, сколько работает, остаток демо-режима; код 1 — рантайм не запущен |
| `python tools/codesys/cds.py runtime restart` | остановить свой процесс и запустить заново |
| `python tools/codesys/cds.py runtime stop` | остановить свой процесс (службу Windows не трогает) |

- `runtime init` создаёт `%USERPROFILE%\.local\plc-tools\cds-runtime\`: `boot.cfg`, `work\` с
  копией штатного `CODESYSControl.cfg` (из `C:\ProgramData\CODESYS\CODESYSControlWinV3\<id>\`, файл
  только читается) и `credentials.json` с пользователем `cdsci` и случайным паролем. Пароль не
  печатается; файл лежит вне репозитория — не копируйте и не коммитьте его.
- Без лицензии рантайм работает 2 часа с момента запуска. `cds.py test` сам перезапускает его, если
  он работает дольше 100 минут (`CODESYS_RUNTIME_MAX_AGE_MIN`). Запуск и остановка — только своего
  процесса (с `-d <boot.cfg>`); если порт 11740 занят службой или чужим экземпляром, `cds.py`
  использует его, но не перезапускает.
- Состояние рантайма (пользователи, загруженные приложения, сертификаты, PlcLogic) из-за
  виртуализации UAC лежит не в `work\`, а в
  `%LOCALAPPDATA%\VirtualStore\Program Files (x86)\CODESYS 3.5.17.30\GatewayPLC\`; туда же
  попадает XML-отчёт coUnit (`%LOCALAPPDATA%\VirtualStore\coUnit_xunit_testresults.xml`).
  Чтобы «обнулить» рантайм (забыть пользователей и приложения), остановите его и удалите этот
  каталог вручную — это необратимо.

**Первый вход и создание пользователя.** Управление пользователями рантайма остаётся включённым
(отключать его не нужно). На свежем рантайме без пользователей `cds.py test` сам создаёт первого
пользователя из `credentials.json` (`set_credentials_for_initial_user` и подключение), если обычный
вход не удался. _Эта ветка реализована по API, но на этой машине не выполнялась: пользователь
`cdsci` уже был создан._ Если автоматически не получится — вручную в IDE: открыть тестовый проект
(раздел 6), «Устройство → Настройки соединения» (Communication Settings), выбрать шлюз `Gateway-1`
(localhost:1217) и устройство, войти — IDE предложит создать пользователя; ввести логин и пароль
из `credentials.json`.

## 5. Импорт, сборка, тесты

Все команды — из корня репозитория (cmd, PowerShell или Git Bash). Каждая запускает CODESYS без
окна (`--noUI`), длится 10–20 секунд и пишет журналы в `build/`.

| Команда | Что делает |
|---|---|
| `python tools/codesys/cds.py import` | `src/` → `build/<имя>.project` (MainTask 20 мс → `PRG_Main`) |
| `python tools/codesys/cds.py import --tests` | `src/` и `tests/` → `build/<имя>-tests.project` (TestTask 10 мс → `PRG_Tests`, coUnit) |
| `python tools/codesys/cds.py build` | импорт и полная сборка: `build/build.log`, `build/build.json` |
| `python tools/codesys/cds.py build --tests` | то же для тестового проекта |
| `python tools/codesys/cds.py test` | импорт с тестами, сборка, прогон в рантайме |
| `python tools/codesys/cds.py roundtrip` | импорт в чистый проект → экспорт → сравнение с `src/` и `tests/` |
| `python tools/codesys/cds.py report` | итоги последнего `test` → `docs/TEST_REPORT.md` |

Что смотреть:

- `import` печатает, что создано, обновлено, удалено и перемещено. Повторный импорт без правок —
  «создано 0, обновлено 0, удалено 0». Ошибки раскладки (коды LAY) — отказ без изменений проекта.
- `build`: ошибки и предупреждения компилятора с файлом и строкой раскладки, например
  `src/POUs/Iiot/F_IiotTopic/F_IiotTopic.impl.st:3: Error C0046 Идентификатор 'sPrefixX' не задан`. Сообщения
  IDE — на русском. Если в IDE видны ошибки, которых нет в выводе, — скопируйте их в
  [BUILD_ERRORS.md](BUILD_ERRORS.md). Перед открытием проекта `cds.py` удаляет кэш предкомпиляции
  `build/<имя>_project.precompilecache`: с ним CODESYS 3.5.17.30 после замены объявления ФБ с
  методами собирал старый текст (сломанное объявление — «0 ошибок», исправленное — старая ошибка).
- `test` перед прогоном удаляет `build/test-results.json` и `build/junit.xml` прошлого запуска:
  при ошибке сборки или входа в рантайм старые зелёные результаты не остаются.
- `test`: итог по наборам и тестам; упавшие — с сообщением coUnit. Результаты — в
  `build/test-results.json` и `build/junit.xml`, журнал — `build/test.log`.
- `roundtrip`: «экспорт совпадает с src/ и tests/ побайтно» и «повторный импорт … — 0 изменений».
  Любой дифф — ошибка скриптов (issue).

Коды выхода: 0 — успех; 1 — ошибки раскладки или сборки, упавшие тесты, дифф roundtrip;
2 — аргументы или `config.json`; 3 — окружение (нет CODESYS, рантайма, файла); 4 — таймаут;
5 — блокировка занята. Рантайм один на машину: команды, которые с ним работают, ждут друг друга
(блокировка `%LOCALAPPDATA%\plc-tools\codesys-runtime.lock`).

## 6. Работа в IDE и экспорт перед коммитом

1. Собрать проект: `python tools\codesys\cds.py import` (или `import --tests` для проекта с тестами).
2. Открыть его в IDE: «Файл → Открыть проект» → `build\<имя>.project` (`build\<имя>-tests.project`),
   либо из консоли cmd (из PowerShell — эту же строку через `cmd /c '<строка>'`: PowerShell и Git
   Bash переставляют кавычки в `--profile="..."`, и CODESYS не находит профиль; `cmd /c` проверен
   с `--noUI --runscript`). `%CODESYS_EXE%` виден в консолях, открытых после `setx`:

   ```bat
   "%CODESYS_EXE%" --profile="CODESYS V3.5 SP17 Patch 3" --project="%CD%\build\plc-iiot-stack.project"
   ```

   Вход в рантайм из IDE: «Онлайн → Логин» с пользователем из `credentials.json`. _Открытие из
   консоли с `--project` здесь не проверялось (ключ описан в справке CODESYS по командной строке)._
3. Править, сохранить проект, **закрыть IDE**. Пока проект открыт в IDE, `import`, `build`, `test`
   и `export` сразу отказываются: «проект … открыт в другом экземпляре CODESYS (пользователь, компьютер,
   PID)», код выхода 3 (проверено). Файл блокировки `<проект>.~u`, оставшийся после сбоя CODESYS
   или его остановки по таймауту, `cds.py` удаляет сам, если процесса с этим PID больше нет.
4. Выгрузить правки в тексты и проверить дифф:

   ```bat
   python tools/codesys/cds.py export
   python tools/codesys/cds.py export --tests
   git diff --stat
   ```

   `export` выгружает `build/<имя>.project` в `src/`; `export --tests` — `build/<имя>-tests.project`
   в `src/` и `tests/`.

Защита от потери правок:

- `import` отказывается перезаписывать проект, сохранённый в IDE после последнего
  `import`/`export`, — сначала `export` (или `--force`, если правки не нужны);
- `export` в репозиторий отказывается, если `src/` (`tests/`) изменились после последнего
  `import`/`export` этого проекта: экспорт удаляет файлы, которых нет в проекте. Сравнить можно
  выгрузкой в отдельный каталог: `cds.py export --to build\cmp`; перезапись — `--force`.

Не входит в раскладку (только в IDE, при экспорте не сохраняется — описывайте здесь и в docs):

- [ ] дерево устройств ПЛК210 и конфигурация модулей ввода-вывода; конфигураторы обмена (Modbus, OPC UA);
- [ ] визуализации, графические языки (FBD/LD/SFC/CFC), действия (`ACTION`) — `export` предупреждает о них;
- [ ] **Persistent Variables** (`*.pvl.st`): в SP17 скриптом не создаются. Создайте объект вручную
  («Application → Добавить объект → Persistent Variables» с именем как у файла), затем
  `cds.py import` обновит его текст из файла, а `export` выгрузит обратно.

Задачи и ссылки на библиотеки не правьте в IDE: их создаёт `import` по `tools/codesys/config.json`
(лишние задачи удаляются).

## 7. Релиз и библиотеки: `.project`, `.library`, зависимости

`.project` и `.library` в git не хранятся — прикладываются к релизу GitHub. Команды этого раздела
проверены на 3.5.17.30 (16.10.2026) на двух временных репозиториях — библиотеке и проекте, который
её использует; сам шаблон собирается в библиотеку `plc-iiot-stack` (`cds.py library`).

### 7.1. Выпуск релиза

1. `python tools\codesys\cds.py build` — 0 ошибок; `python tools\codesys\cds.py test` — тесты зелёные.
2. Версия: `library.version` в `tools/codesys/config.json` (четыре числа, `1.2.0.0`) и запись в
   `CHANGELOG.md`. Компанию (`library.company`) и название (`library.title`) после первого релиза не
   меняйте: по тройке «компания, название, версия» библиотеку находят проекты-потребители.
   Перед публикацией шаблона замените `plc-portfolio` на свой GitHub-логин (без символов
   `<>:"/\|?*,()`).
3. Библиотека (для репозиториев-библиотек):

   ```bat
   python tools\codesys\cds.py library --compiled --released
   ```

   Итог — `build\<имя>.library` (с исходниками) и `build\<имя>.compiled-library` (без исходников),
   Project Information — из раздела `library`, проверка «все объекты пула» — 0 ошибок. Ошибки
   выводятся с файлом и строкой в `src/`; при ошибках файлы не устанавливаются (код 1), а
   `build\<имя>.library` можно открыть в IDE и посмотреть. Ссылки самой библиотеки
   (`library.libraries`: `Standard`, другая библиотека портфолио) `cds.py` добавляет и в проекты
   приложения и тестов этого репозитория — в `modes` их повторять не нужно.
4. Приложить к релизу GitHub: `.compiled-library` — для использования, `.library` — для отладки и
   чтения исходников; `build\<имя>.project` — рабочий проект (для переноса на другую машину удобнее
   «Файл → Архив проекта → Сохранить/Отправить архив», `.projectarchive`).
5. Поставить тег `v1.2.0` на коммит релиза: потребители переключают на него соседний репозиторий
   (раздел 7.3), а `cds.py` проверяет, что версия в его `config.json` совпадает с закреплённой.
6. Записать в [TEST_REPORT.md](TEST_REPORT.md) итоги (`cds.py report`).

То же в IDE (если `cds.py` недоступен): открыть `build\<имя>.library` (или проект), заполнить
«Проект → Информация о проекте» (компания, название, версия, пространство имён по умолчанию),
выполнить «Сборка → Проверить все объекты пула» и «Файл → Сохранить проект как скомпилированную
библиотеку». _Названия пунктов меню — сверить с русской IDE 3.5.17.30; в IDE этот путь не
выполнялся, проверен только скриптовый._

### 7.2. Установка библиотеки в репозиторий библиотек

- Своя библиотека из репозитория-библиотеки: `python tools\codesys\cds.py library --install`
  (с `--compiled` ставится `.compiled-library`). Та же версия заменяется, другие версии остаются
  рядом. Репозиторий — `System` (`C:\ProgramData\CODESYS\Managed Libraries`), другой — по имени в
  `CDS_LIBRARY_REPOSITORY`.
- Файл, полученный готовым (релиз GitHub): в IDE «Инструменты → Репозиторий библиотек → Установить»
  или путь к файлу в переменной из `install_from` (например, `setx PL_LIBRARY "C:\dl\plc-process-lib.compiled-library"`)
  и `python tools\codesys\cds.py deps` — файл поставится, если нужной версии ещё нет.
- Удаление: `python tools\codesys\cds.py library --uninstall` (версия из `config.json`) или
  `--uninstall --all-versions` — в репозитории-библиотеке; в IDE — «Репозиторий библиотек →
  Удалить». Удалять стоит и временные версии, поставленные для экспериментов.
- Установленные версии и откуда они: `python tools\codesys\cds.py deps` в проекте-потребителе
  (строка «установлена cds.py из <рабочая копия> @ <коммит>»).

### 7.3. Проект, который использует библиотеку портфолио

1. Клонировать репозиторий библиотеки рядом: `..\plc-process-lib` (или задать путь в переменной из
   `build_from_repo`, например `PL_REPO`) и переключить его на нужный тег.
2. Описать библиотеку в `tools/codesys/config.json` и сослаться на неё из режимов:

   ```json
   "libraries": {
     "plc-process-lib": {
       "namespace": "PL",
       "title_contains": "plc-process-lib",
       "version": "1.0.0.0",
       "build_from_repo": {"env": "PL_REPO", "default": "../plc-process-lib"},
       "install_from": {"env": "PL_LIBRARY", "default": null}
     }
   },
   "modes": {
     "normal": {"tasks": [...], "libraries": ["plc-process-lib"]},
     "test": {"tasks": [...], "libraries": ["counit", "plc-process-lib"]}
   }
   ```

   В коде — с пространством имён: `fbPump : PL.FB_Pump;`.
3. Версия: **точная** (`"1.0.0.0"`) — для релизов, сборка воспроизводима; **`"*"`** — новейшая из
   установленных (по номеру версии), удобно, пока библиотека и проект разрабатываются вместе.
   Смена закрепления — правка `version` и `cds.py build`: ссылка в проекте заменится.
4. `python tools\codesys\cds.py build` (или `test`). Если нужной версии нет в репозитории
   библиотек, `cds.py` соберёт её в соседнем репозитории (`cds.py library --install` там) и повторит
   задание. Если соседний репозиторий собирает другую версию — отказ с подсказкой (переключить его
   на тег или изменить `version`). Библиотека проверяется и по её собственным зависимостям: если
   их нет в репозитории библиотек, она пересобирается в соседнем репозитории вместе с ними.
   Явно: `cds.py deps` (проверить и доустановить),
   `cds.py deps --rebuild plc-process-lib` (пересобрать после правок в библиотеке),
   `cds.py deps --check` (только проверить). `--no-deps` у `build`/`test` отключает автосборку.
5. Плейсхолдер вместо прямой ссылки — `"placeholder": "plc-process-lib"` в описании: `cds.py`
   добавит `#plc-process-lib` с перенаправлением на закреплённую версию.

### 7.4. Параллельные рабочие копии (git worktree)

У каждой рабочей копии свои `build/` и блокировка, сборки идут параллельно; тесты в рантайме и
установка библиотек — по очереди (общие блокировки в `%LOCALAPPDATA%\plc-tools\`). Переменные
`CDS_PROJECT*`, `CDS_LIBRARY*`, `CDS_REPO_ROOT`, `CDS_CONFIG` задавайте только в консоли
(`set CDS_LIBRARY_VERSION=1.0.1.0`), не через `setx`: из реестра `cds.py` их не читает, иначе они
действовали бы на все копии. Библиотека одной версии из двух копий — одна запись в репозитории
библиотек (действует последняя установка, `cds.py` предупреждает): для экспериментов в отдельной
копии собирайте без `--install` или с другой версией.

## 8. Зеркало на GitVerse или GitFlic

1. Создать пустой репозиторий на GitVerse или GitFlic (без README и лицензии).
2. Добавить его как второй remote и отправить все ветки и теги:

   ```bash
   git remote add mirror <url-зеркала>
   git push mirror --all
   git push mirror --tags
   ```

3. После каждого релиза повторять `git push mirror --all` и `git push mirror --tags`.

## 9. Библиотека CODESYS-MQTT

ПЛК-часть стека работает с транспортом через интерфейс `I_MqttClient`
([plc_mqtt.md](plc_mqtt.md#адаптер-i_mqttclient)). Готовый адаптер написан для открытой библиотеки
[CODESYS-MQTT](https://github.com/stefandreyer/CODESYS-MQTT) (Stefan Dreyer), но **на CODESYS 3.5.17.30
с ней не собирается**: у библиотеки нет зависимостей. Поэтому библиотека в проект не подключена,
адаптер лежит вне `src/` (`adapters/sd_mqtt_1_0/`), а `PRG_Iiot` по умолчанию работает с клиентом без
транспорта.

### 9.1. Что известно о библиотеке (проверено 16.10.2026)

| Параметр | Значение |
|---|---|
| Лицензия | MIT (файл `LICENSE` в архиве релиза, «Copyright (c) 2018 stefandreyer») — совместима с репозиторием; библиотека в git не хранится |
| Последний релиз GitHub | `stable` («Resovled static IP Problems», 26.09.2018), до него `1.0` (14.09.2018). Файлов-приложений у релизов нет — только архив исходников `CODESYS-MQTT-stable.zip` (SHA-256 `485a7de80ab42100ed39eacad4e37a6e5ff10d9011fa8112a4ab7ee74e08e7d6`) |
| Библиотека в релизе | `MQTT.library`: Project Information — MQTT 1.0.0.0, компания Stefan Dreyer, пространство имён и плейсхолдер `SD_MQTT`, `qualified-access-only` |
| Новые версии | в ветке `master` — файлы `MQTT 1.1.0.2…1.2.0.7.library` (последний коммит с библиотекой — 11.11.2023, README упоминает переход на 3.5.16.30). Это не релиз; по правилам проекта брались только файлы официального релиза, поэтому 1.2.x не скачивались и не проверялись |
| Возможности (README) | QoS 0–2, will topic, retain, неограниченное число ФБ публикации и подписки, TLS без проверки сертификатов |
| Зависимости 1.0.0.0 | OSCAT BASIC 3.3.3.0, OSCAT NETWORK 1.30, CommonTypsFunctions (Stefan Dreyer, github.com/stefandreyer), системные библиотеки точных версий: 3S Storage 3.5.13.0, CAA File 3.5.13.0, CAA Memory 3.5.12.0, CmpCrypto 3.5.11.0, MemoryUtils 3.5.13.0, StringUtils 3.5.13.0, SysMem23 3.5.13.0, SysProcess 3.5.7.0, SysSem 3.5.5.0, SysStr23 3.5.13.0, SysTarget 3.5.5.0, Time and Date 3.5.7.0 |

Компиляция на 3.5.17.30 (проект с адаптером и ссылкой `MQTT, 1.0.0.0 (Stefan Dreyer)`, CODESYS
Control Win V3): 15 предупреждений «библиотека … не найдена» (список выше) и 384 ошибки — все в коде
библиотеки, в файлах адаптера сообщений нет. При таком числе ошибок это ещё не доказывает, что адаптер
собирается: **адаптер с библиотекой не компилировался и на брокере не проверялся**.

Библиотека 1.0.0.0 не передаёт брокеру логин и пароль, а брокер стенда анонимный доступ запрещает
([data_schema.md, 2.3](data_schema.md#23-права-acl-брокера)): даже с зависимостями эта версия к
стенду не подключится. Адаптер в этом случае отказывает в `Connect` (`MQTT_ERR_AUTH_UNSUPPORTED`), а не
подключается без пароля.

### 9.2. Установка (если зависимости есть)

1. Скачать архив официального релиза: GitHub → Releases → `stable` → «Source code (zip)». Распаковать
   в отдельную пустую папку (например, `%USERPROFILE%\Downloads\codesys-mqtt\stable\`), сверить
   SHA-256 архива с таблицей выше.
2. Установить зависимости (OSCAT BASIC и NETWORK — с oscat.de или из репозиториев автора,
   CommonTypsFunctions — github.com/stefandreyer) и системные библиотеки нужных версий (если их нет в
   установленном CODESYS — пакеты CODESYS тех версий). Без них дальнейшие шаги дают ошибки сборки из
   9.1.
3. Установить `MQTT.library` одним из способов:
   - в IDE: «Инструменты → Репозиторий библиотек → Установить» (Tools → Library Repository → Install);
   - или через `tools/codesys/config.json` — описание библиотеки с `install_from`, путь к файлу — в
     переменной окружения (`setx SD_MQTT_LIBRARY "C:\...\MQTT.library"`):

     ```json
     "sd_mqtt": {
       "label": "CODESYS-MQTT (релиз stable, SD_MQTT 1.0.0.0)",
       "title": "MQTT",
       "company": "Stefan Dreyer",
       "version": "1.0.0.0",
       "install_from": {"env": "SD_MQTT_LIBRARY", "default": null}
     }
     ```

     и `"sd_mqtt"` в `modes.normal.libraries`; `python tools\codesys\cds.py deps` поставит файл в
     репозиторий `System`, если этой версии ещё нет. Тест `test_codesys_config_of_this_project`
     (`tests_stack/test_plc_contract.py`) сейчас требует, чтобы `sd_mqtt` в `config.json` не было, —
     при подключении библиотеки поправьте его.
4. Перенести адаптер в сборку: `adapters\sd_mqtt_1_0\src\POUs\Adapters\` → `src\POUs\Adapters\`.
5. Задать адаптер до первого вызова `PRG_Iiot` (в `PRG_Main`):

   ```
   VAR
       fbMqtt : FB_MqttClientSdMqtt;
   END_VAR

   PRG_Iiot.itfClientOverride := fbMqtt;
   PRG_Iiot();
   ```

6. `python tools\codesys\cds.py build` — 0 ошибок; затем проверка на брокере стенда (раздел 9.3).

Удаление: «Репозиторий библиотек» → `MQTT 1.0.0.0 (Stefan Dreyer)` → «Удалить». _На этой машине
`MQTT.library` 1.0.0.0 из релиза `stable` установлена в репозиторий `System` скриптом
(`librarymanager.install_library`) для проверки компиляции и не удалена — удалите её, если
библиотека не нужна._

### 9.3. Проверка на брокере (не выполнялась)

1. Стенд: `make env`, `make up` (Windows — `tools_project\make.ps1`), в `.env` — `MQTT_PLC_USER`,
   `MQTT_PLC_PASSWORD`.
2. В IDE, в онлайн-режиме, задать `GVL_Iiot.stIiotCfg.stBroker` (`sHost` — адрес компьютера со
   стендом, `uiPort` 1883, логин и пароль) и `xEnable := TRUE`. Пароль в проект и в git не
   записывается — только значение в онлайн-режиме или Persistent Variables на объекте.
3. Ожидаемо: `GVL_Iiot.stIiotSts.eConnState = Connected`, `eNe107 = Good`; в брокере —
   `vodokanal/kns1/station/PLC1/status/connection` с `online`/`birth`, затем метрики
   (`mosquitto_sub -v -t 'vodokanal/#'` с учётной записью оператора).
4. Команды: `xCommandsEnable := TRUE`, команда из Node-RED или `mosquitto_pub` по
   [data_schema.md, 5.1](data_schema.md#51-сообщение-и-проверки) — ответ в `…/cmd_ack/<Command>`.

## 10. Символьная конфигурация для OPC UA

Что видно клиентам OPC UA-сервера CODESYS (Telegraf, SCADA, `kns-report`), задаёт объект Symbol
Configuration приложения с включённой опцией «Support OPC UA features». Узлы, которые читает стенд, —
переменные флагмана КНС-1; во флагмане объект создаёт и настраивает его импорт по правилам
`tools_project/codesys/symbol_rules.json` (DESIGN 13 флагмана), вручную ничего делать не нужно.

Что нужно стенду из этих правил (полный перечень узлов — `telegraf/telegraf.d/opcua.conf`, 133 узла):

| Что выгружается во флагмане | Доступ | Что берёт стенд |
|---|---|---|
| `GVL_Devices` — все экземпляры `fb<TAG>` | чтение | состояние и значения устройств (`stSts`, `xRunning`, `xValue`) |
| `GVL_Hmi.st<TAG>Cmd`, `xApplyProjectCfg` | чтение и запись | команды устройствам (SCADA по OPC UA; по MQTT их пишет `PRG_Iiot`) |
| `GVL_IO` — все | чтение | `uiP101_FCODE`…`uiP103_FCODE`, `xK1` |
| `GVL_Station.stStationSts`, `fbLIC101` | чтение | станция KNS1 и регулятор LIC101 |
| `GVL_Station.stStationCmd`, `stLIC101Cmd` | чтение и запись | команды станции и регулятора |
| `GVL_Log`, `GVL_Persist`, `GVL_Sim`, `GVL_Time` | по правилам флагмана | стенд не читает |
| `GVL_Iiot.stIiotCfg`, `GVL_Iiot.stIiotSts` | чтение (атрибут `{attribute 'symbol' := 'read'}` в исходнике) | настройки и состояние MQTT для HMI; после встраивания — правило в `symbol_rules.json` флагмана (раздел 11, шаг 6) |

Пароль брокера `stIiotCfg.stBroker.sPassword` помечен `{attribute 'symbol' := 'none'}` и не выгружается
даже вместе со структурой. Узлы сервера: `ns=4;s=|var|<устройство>.Application.<GVL>.<путь>`, например
`ns=4;s=|var|CODESYS Control Win V3.Application.GVL_Station.stStationSts.eMode` (имя устройства у ПЛК210 —
другое, сверить по обзору сервера; [ASSUMPTIONS.md](ASSUMPTIONS.md), E11). Что каждый узел стенда есть в
символах флагмана с тем же типом, проверяет `tests_stack/test_flagship_binding.py` по снимку его
интерфейса; обзор сервера живым клиентом — раздел 12.

### 10.1. В IDE

1. Открыть проект флагмана. «Application → Добавить объект → Символьная конфигурация» (Add Object →
   Symbol Configuration), отметить «Support OPC UA features», «Клиентская раскладка» — оптимизированная
   (Optimized layout).
2. «Собрать» (Build) в редакторе символьной конфигурации — появится дерево переменных.
3. Отметить переменные по таблице выше, доступ — в столбце «Права доступа» (Access Rights).
4. Сохранить проект, «Онлайн → Логин» и загрузка. Права пользователей рантайма на объект
   `OPCUAServer` — [security.md](security.md), раздел 3.2.

_Названия пунктов меню — сверить с русской IDE 3.5.17.30; этот путь в IDE не проходился: во флагмане
объект создаёт скрипт (10.2)._

### 10.2. Скриптом

Символьную конфигурацию создают и настраивают из CODESYS Scripting (`ScriptSymbolConfigObject`, есть с
3.5.10): `application.create_symbol_config(export_comments_to_xml, support_opc_ua,
client_side_layout_calculator)`, доступ — свойство `configured_access` переменных из
`get_all_signatures()`. Объект сохраняется в `.project`, но не в `src/`: после пересоздания проекта —
повторить. Во флагмане это делает `tools_project/codesys/symbol_config.py` по `symbol_rules.json` (его
основа — скрипт ниже); прогон 19.10.2026 по данным флагмана: `GVL_Devices` — 29 Read, `GVL_Hmi` — 30
ReadWrite, `GVL_IO` — 86 Read.

Исходный скрипт этого репозитория (IronPython 2.7; проект — в переменной `IIOT_PROJECT`); проверен
16.10.2026 на копии `build\plc-iiot-stack.project`, когда ПЛК-часть собиралась здесь с заглушкой
флагмана (`KnsShim`, удалена при привязке к флагману):

```python
# -*- coding: utf-8 -*-
from __future__ import print_function
import os
from System import Guid

OPTIMIZED_LAYOUT = Guid("{0141eb75-141b-4ea1-9a8c-75f952b22a6c}")  # OptimizedOutputOffsetCalculator
GVL_IO_VARS = ("uiP101_FCODE", "uiP102_FCODE", "uiP103_FCODE", "xHA1", "xHL1", "xK1")


def wanted(gvl, var):
    if gvl == "GVL_Devices":
        return SymbolAccess.Read
    if gvl == "GVL_Hmi":
        if var.startswith("st") and var.endswith("Cmd"):
            return SymbolAccess.ReadWrite
        return SymbolAccess.Read
    if gvl == "GVL_IO" and var in GVL_IO_VARS:
        return SymbolAccess.Read
    return None


proj = projects.open(os.environ["IIOT_PROJECT"], primary=True)
app = proj.active_application
found = [c for c in app.get_children(False) if c.is_symbol_config]
if found:
    sc = found[0]
else:
    sc = app.create_symbol_config(False, True, OPTIMIZED_LAYOUT)  # комментарии в XML — нет, OPC UA — да
changed = 0
for sig in sc.get_all_signatures(True):  # True — собрать приложение
    gvl = sig.full_qualified_name.split(".")[-1]
    for v in sig.variables:
        access = wanted(gvl, v.name)
        if access is not None and v.configured_access != access:
            v.configured_access = access
            changed += 1
print("symbol_config: изменено переменных", changed)
app.build()
proj.save()
proj.close()
```

Тогда по файлу символов (`<проект>.Device.Application.xml`, настройки `SupportOPCUA,
LayoutCalculator=OptimizedClientSideLayoutCalculator`): `GVL_Devices` — 29 переменных `Read`, `GVL_Hmi` —
29 структур команд `ReadWrite` и `xApplyProjectCfg` `Read`, `GVL_IO` — 6 `Read`, `GVL_Iiot` — 2 `Read`
(по атрибутам); в типе `ST_MqttBrokerCfg` 10 полей из 11 — `sPassword` нет.

## 11. Встраивание во флагман

ПЛК-часть стека — две части ([plc_mqtt.md](plc_mqtt.md#привязка-к-флагману)): ядро в `src/` (от
флагмана не зависит) и привязка в `flagship/src/` (`PRG_Iiot`, сгенерированный `FB_IiotKnsMap` — пути
к переменным флагмана, типы `PL.*`). Встраивание — копирование обеих в репозиторий kns-pump-station.

1. **Сверить снимок.** `python tools_project/flagship_snapshot.py --check` (флагман рядом, `../kns-pump-station`,
   или путь в `KNS_REPO`): «снимок актуален» — пути привязки совпадают с флагманом. Есть расхождения —
   `python tools_project/flagship_snapshot.py`, затем `python tools_project/gen_plc_iiot.py`,
   `python tools_project/gen_config.py` и `python -m pytest tests_stack` (проверки привязки).
2. **Скопировать ST** в `src/` флагмана: из этого репозитория — `src/` без `src/POUs/PRG_Main` (у флагмана
   свои программы задач) и `flagship/src/` целиком (`POUs/Iiot/PRG_Iiot`, `POUs/Iiot/FB_IiotKnsMap`).
   Каталоги `src/POUs/Iiot` обеих частей сливаются.
3. **Константы.** `src/GVLs/GVL_Const.gvl.st` этого репозитория — раздел «IIoT» в `GVL_Const` флагмана
   (один файл на проект). Пересечений имён нет (сверено с флагманом `main` при снятии снимка); коды
   plc-process-lib привязка берёт из самой библиотеки (`PL.GVL_Const.MOT_FLT_COMM_LOSS`,
   `MOT_WRN_COMM_LOSS`, `PL.E_DeviceMode.OutOfService`). `src/GVLs/GVL_Iiot.gvl.st` и
   `src/GVLs/Generated/GVL_IiotMap.gvl.st` копируются как есть.
4. **Задача и библиотеки** (`tools/codesys/config.json` флагмана): `PRG_Iiot` — в `MainTask` после
   `PRG_Devices` (значения устройств текущего цикла, команда из `GVL_Hmi` и `GVL_Station` выполняется в
   следующем цикле, как команда с HMI); библиотека `systimertc` у флагмана уже подключена.
5. **Клиент MQTT.** Без адаптера `PRG_Iiot` работает с клиентом без транспорта: обмена нет, состояние —
   «нет связи». Адаптер на библиотеку MQTT ПЛК — раздел 9, присваивание
   `PRG_Iiot.itfClientOverride := fbMyClient;` до первого вызова.
6. **Символы.** `GVL_Iiot` — правило `{"gvl": "GVL_Iiot", "vars": ["stIiotCfg", "stIiotSts"], "access":
   "Read"}` в `tools_project/codesys/symbol_rules.json` флагмана (сейчас там «по атрибутам проекта 06 после
   встраивания»); сверить по файлу символов, что `sPassword` не выгружается.
7. **Тесты.** Наборы `tests/` этого репозитория переносятся вместе с `FB_MqttClientFake` и `F_TestContains`;
   в `PRG_Tests` флагмана — их экземпляры. Набор `FB_IiotMap_Test` проверяет таблицы, тест привязки на
   настоящих ФБ флагмана — дальнейший шаг (сейчас пути проверяет pytest по снимку).
8. **Сборка и прогон во флагмане:** `cds.py build --tests`, `cds.py test`; затем раздел 12 — живой обмен.

_Встраивание не выполнялось: флагман в этой работе не собирался (его рантайм занят прогоном ПМИ).
Компиляцию `PRG_Iiot` и `FB_IiotKnsMap` с типами `PL.*` проверит только сборка во флагмане._

## 12. Стенд против флагмана в CODESYS (OPC UA)

Путь OPC UA работает с флагманом без встраивания: Telegraf читает узлы символьной конфигурации
приложения имитации флагмана. Путь MQTT (публикация из ПЛК и команды) — только после встраивания
`PRG_Iiot` (раздел 11) с адаптером MQTT (раздел 9).

1. **Флагман в имитации.** В репозитории kns-pump-station (один раз — `python tools/codesys/cds.py runtime
   init`): `python tools_project/codesys/sim.py start` — импорт, символьная конфигурация сборки `sim`,
   рантайм, сертификат OPC UA-сервера, загрузка и «Старт» приложения имитации (подробно — DESIGN 16 и
   MANUAL_STEPS флагмана). Сервер предлагает Basic256Sha256 (Sign, SignAndEncrypt) со входом по имени и
   паролю.
2. **Настройки стенда** в `.env`:

   ```ini
   # docker compose: OPC UA-сервер на хосте; локальный стенд без Docker: opc.tcp://127.0.0.1:4840
   OPCUA_ENDPOINT=opc.tcp://host.docker.internal:4840
   OPCUA_SECURITY_POLICY=Basic256Sha256
   OPCUA_SECURITY_MODE=SignAndEncrypt
   OPCUA_AUTH_METHOD=UserName
   OPCUA_USERNAME=<пользователь рантайма с правом чтения>
   OPCUA_PASSWORD=<его пароль>
   ```

3. **Стенд без эмулятора:** `make up` (docker compose) или
   `powershell -ExecutionPolicy Bypass -File tools_project\local_stack.ps1 start` (без `-Emulator`).
4. **Доверие сертификату Telegraf.** Первое подключение сервер отклоняет: сертификат клиента — в
   карантине рантайма. Перенести его в доверенные (экран безопасности IDE или хранилище `.pki`
   рантайма; [security.md](security.md#42-сертификаты-и-списки-доверия)) и перезапустить рантайм; у
   Telegraf сертификат в томе `telegraf-pki` сохраняется, доверие — один раз.
5. **Проверка.** Grafana, переменная «Источник» = `opcua`: уровень, насосы, станция. Сколько узлов
   пишут данные (ожидается 133 — все узлы каталога), — запрос в Data Explorer InfluxDB или
   `influx query`:

   ```flux
   from(bucket: "kns_raw") |> range(start: -2m)
     |> filter(fn: (r) => r._measurement == "telemetry" and r.source == "opcua" and r._field == "value")
     |> last() |> group() |> count()
   ```

   Тревоги, команды по MQTT и узел PLC1 без встраивания `PRG_Iiot` не появятся: они идут по MQTT.

_Не проверялось: стенд с настоящим рантаймом флагмана не соединялся (рантайм занят прогоном ПМИ).
Что сверить при первом прогоне: номер пространства имён и префикс узлов (`OPCUA_NAMESPACE`,
`OPCUA_ID_PREFIX`), политику и вход по имени, доверие сертификату Telegraf, все 133 узла со статусом
`StatusGood`, совпадение типов (перечисления флагмана — Int16), инверсию `K1/general_alarm`._
