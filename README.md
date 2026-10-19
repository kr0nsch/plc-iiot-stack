<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/media/banner-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/media/banner-light.svg">
    <img alt="Баннер plc-iiot-stack: цепочка PLC — OPC UA — MQTT — InfluxDB — Grafana, стрелочный прибор и тренд" src="docs/media/banner-light.svg" width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/<GITHUB_USER>/plc-iiot-stack/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/<GITHUB_USER>/plc-iiot-stack/ci.yml?branch=main&style=flat-square&label=CI&labelColor=1B2736"></a>
  <a href="LICENSE"><img alt="Лицензия MIT" src="https://img.shields.io/badge/license-MIT-56677D?style=flat-square&labelColor=1B2736"></a>
  <img alt="CODESYS 3.5.17" src="https://img.shields.io/badge/CODESYS-3.5.17-C2410C?style=flat-square&labelColor=1B2736">
  <img alt="IEC 61131-3" src="https://img.shields.io/badge/IEC%2061131--3-56677D?style=flat-square">
  <img alt="Тесты: 87 coUnit в CODESYS и 12 интеграционных тестов стенда" src="https://img.shields.io/badge/tests-87%20coUnit%20%C2%B7%2012%20stack-3A4B60?style=flat-square&labelColor=1B2736">
  <img alt="Язык: Python" src="https://img.shields.io/badge/Python-3A4B60?style=flat-square&logo=python&logoColor=white">
  <img alt="Язык: Structured Text" src="https://img.shields.io/badge/Structured%20Text-3A4B60?style=flat-square">
</p>

<p align="center">
  <a href="#демонстрация">Демо</a> ·
  <a href="#архитектура">Архитектура</a> ·
  <a href="#быстрый-старт">Быстрый старт</a> ·
  <a href="docs/">Документация</a> ·
  <a href="#summary-en">Summary (EN)</a>
</p>

**От датчика до дашборда.** Воспроизводимый IIoT-стенд для канализационной насосной станции КНС-1
(флагман портфолио): данные ПЛК на CODESYS по MQTT и OPC UA попадают в InfluxDB 2 и на дашборды
Grafana, а команды оператора идут обратно и проверяются в ПЛК по белому списку. Инфраструктура
описана кодом (docker compose), стенд работает и без ПЛК — на эмуляторе с теми же тегами, что у
флагмана. Сторона ПЛК — код ST для CODESYS 3.5.17.30: публикация телеметрии и тревог, шлюз команд,
диагностика связи.

## Демонстрация

Всё ниже снято на машине разработки с реальных прогонов: локальный стенд без Docker
(`tools_project/local_stack.ps1`, те же конфигурации, что в docker compose), эмулятор ПЛК вместо
железа, CODESYS 3.5.17.30 и CODESYS Control Win V3. Макетов нет.

<p align="center">
  <img alt="Дашборд Grafana «КНС-1: обзор станции» наполняется данными эмулятора ПЛК: уровень LT101 с зонами LL, L, H, HH — приток поднимает его выше H 3.5 м, насосы откачивают; расход, давление, скорость и состояние трёх насосов" src="docs/media/demo-grafana-overview.gif" width="900">
</p>
<p align="center"><sub>Grafana 12.4.12 на локальном стенде: кадр раз в 15 с в течение 14 мин, окно «последние 15 минут»; модельное время эмулятора ускорено в 60 раз</sub></p>

<table>
<tr>
<td width="50%"><a href="docs/media/shot-grafana-pumps-light.png"><img alt="Дашборд «Насосы: моточасы и пуски»: наработка и пуски P101–P103 всего, за выбранный период и по суткам" src="docs/media/shot-grafana-pumps-top-light.png" width="100%"></a></td>
<td width="50%"><a href="docs/media/shot-grafana-alarms-light.png"><img alt="Дашборд «Тревоги за период»: срабатывания за период и в час, распределение по приоритетам, топ-10 тревог и активная внешняя авария насоса P101" src="docs/media/shot-grafana-alarms-top-light.png" width="100%"></a></td>
</tr>
<tr>
<td align="center"><sub>«Насосы: моточасы и пуски» за последние 30 минут (≈ 30 ч модельного времени)</sub></td>
<td align="center"><sub>«Тревоги за период»: события ISA-18.2, восстановленные из слов тревог устройств</sub></td>
</tr>
</table>

<details>
<summary>Полные снимки трёх дашбордов — обзор станции в момент аварии насоса P101</summary>
<p align="center"><img alt="Дашборд «КНС-1: обзор станции» целиком в момент аварии P101: общая авария K1, состояние «Отказ», активная тревога P101.EXT и статус NE 107 «F — отказ»; ниже коллектор, электроснабжение и газоанализ" src="docs/media/shot-grafana-overview-light.png" width="100%"></p>
<p align="center"><img alt="Дашборд «Насосы: моточасы и пуски» целиком: наработка, пуски, пуски за скользящий час, ток двигателей IT111–IT131, состояние насосов и счётчики до ТО" src="docs/media/shot-grafana-pumps-light.png" width="100%"></p>
<p align="center"><img alt="Дашборд «Тревоги за период» целиком: показатели, распределение по часам и приоритетам, топ-10, текущее состояние и журнал событий тревог" src="docs/media/shot-grafana-alarms-light.png" width="100%"></p>
<p align="center"><sub>Снято подряд, окно «последние 30 минут»; авария ПЧ насоса P101 (тревога P101.EXT) — событие автоматического сценария отказов эмулятора, <code>emulator/iiot_emulator/faults.py</code></sub></p>
</details>

<p align="center">
  <img alt="Запуск локального стенда с эмулятором ПЛК: брокер MQTT, InfluxDB, Telegraf, Grafana и эмулятор готовы, данные на дашбордах; затем 12 интеграционных тестов стенда пройдены" src="docs/media/demo-local-stack-tests.gif" width="900">
</p>
<p align="center"><sub>Запуск стенда и интеграционные тесты: реальный вывод PowerShell, снят term2gif.py; паузы ожидания сокращены</sub></p>

<p align="center">
  <img alt="Сборка ПЛК-части в CODESYS V3.5 SP17 Patch 3: импорт исходников, 0 ошибок и 0 предупреждений, 87 тестов coUnit в 8 наборах пройдены в CODESYS Control Win V3" src="docs/media/demo-codesys-tests.gif" width="900">
</p>
<p align="center"><sub>Импорт, сборка и тесты coUnit одной командой <code>cds.py test</code>: реальный прогон CODESYS 3.5.17.30, ожидание сборки сокращено</sub></p>

## Архитектура

```mermaid
flowchart LR
    subgraph src["Источник данных"]
        plc["ПЛК КНС-1, CODESYS 3.5.17.30<br/>plc-process-lib, src/ этого репозитория"]
        emu["эмулятор ПЛК<br/>emulator/ (Python, asyncua, paho-mqtt)"]
    end
    subgraph stack["Стенд: docker compose"]
        mq["Mosquitto 2.0<br/>пароли, ACL, TLS по флагу"]
        tg["Telegraf 1.39<br/>mqtt_consumer ×5, opcua"]
        db[("InfluxDB 2.9<br/>kns_raw 30 сут · kns_agg 730 сут")]
        gf["Grafana 12.4<br/>3 дашборда из JSON"]
    end
    op["оператор<br/>Node-RED, HMI, тесты"]
    rep["суточный отчёт<br/>report/ → CSV, XLSX"]

    plc -- "MQTT: телеметрия, тревоги,<br/>cmd_ack, status (JSON по схеме)" --> mq
    emu -. "то же без ПЛК" .-> mq
    plc -- "OPC UA: символьная конфигурация" --> tg
    emu -. "OPC UA: те же узлы" .-> tg
    mq --> tg --> db --> gf
    db --> rep
    op -- "cmd" --> mq
    mq -- "cmd → белый список,<br/>диапазоны, возраст, повтор" --> plc
    mq -. "cmd" .-> emu
```

- **Схема данных** — топики `site/area/unit/device/metric` (`vodokanal/kns1/station/LT101/level`),
  JSON Schema 2020-12 на каждый класс сообщений и `schema_version` в каждом сообщении:
  [docs/data_schema.md](docs/data_schema.md), машиночитаемая часть — `schema/`. Имена устройств и
  путей ПЛК — из перечня сигналов флагмана (генератор iolistgen), не придуманы здесь.
- **Два пути в одну модель хранения**: ПЛК публикует MQTT сам (по изменению с зоной нечувствительности
  и раз в 60 с), Telegraf параллельно опрашивает OPC UA. Оба пишут `telemetry` с тегом `source`.
- **Команды** проходят 10 проверок по порядку контракта (retain, схема, версия, топик, белый список,
  диапазон, возраст, повтор, частота, ответ устройства) и получают ровно один ответ `cmd_ack`.
- **InfluxDB 2, а не TimescaleDB** — обоснование и риски (Flux не развивается) в
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#4-выбор-базы-influxdb-2-а-не-timescaledb).

## Быстрый старт

`make demo` — стенд с эмулятором за 5 минут. Нужны Docker с compose v2 и Python 3.11+. ПЛК и CODESYS не нужны: данные даёт эмулятор.

```bash
git clone https://github.com/<GITHUB_USER>/plc-iiot-stack.git && cd plc-iiot-stack
python -m pip install -r requirements-dev.txt
make demo          # .env со случайными паролями, сборка эмулятора, стенд, ожидание данных (до 300 с)
```

`make demo` завершается, когда в InfluxDB есть телеметрия, узел PLC1 сообщил о рождении и Grafana
видит три дашборда. Дальше — http://localhost:3000 (логин и пароль — `GRAFANA_ADMIN_*` в `.env`),
`make test-stack` — интеграционные тесты, `make down` — остановка, `make clean` — с удалением данных.
На Windows с Docker Desktop — те же цели: `powershell -File tools_project\make.ps1 demo`.

| Цель | Что делает |
|---|---|
| `make up` | брокер, InfluxDB, Telegraf, Grafana — данные от настоящего ПЛК (CODESYS Control Win или ПЛК210) |
| `make demo` | то же и эмулятор ПЛК (профиль `demo`) |
| `make up TLS=1` / `DEV=1` | слушатель MQTT TLS 8883 (`make certs` — локальный УЦ) / порт InfluxDB на 127.0.0.1 для отчёта |
| `make test` / `make test-stack` | юнит-тесты / интеграционные тесты и проверка панелей на поднятом стенде |
| `make gen` | перегенерировать узлы OPC UA, тексты тревог, дашборды и таблицы схемы из `schema/` |

### Без Docker: локальный стенд на Windows

Для компьютера без Docker и без прав администратора — те же конфигурации на официальных сборках
для Windows тех же версий (InfluxDB 2.9.1, Telegraf 1.39.3, Grafana 12.4.12; SHA-256 сверяется) и
брокере [amqtt](https://github.com/Yakifo/amqtt) вместо Mosquitto (его Windows-сборка ставится только
установщиком с правами администратора):

```powershell
powershell -ExecutionPolicy Bypass -File tools_project\local_stack.ps1 install          # один раз
powershell -ExecutionPolicy Bypass -File tools_project\local_stack.ps1 start -Emulator  # стенд и эмулятор
python -m pytest -m stack tests_stack                                                     # интеграционные тесты
powershell -ExecutionPolicy Bypass -File tools_project\local_stack.ps1 stop
```

Окружение каждого сервиса берётся из `docker-compose.yml` и `.env`, адреса и пути переводятся на
хост; чем локальный стенд отличается от compose — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#10-локальный-стенд-без-docker).

## Сторона ПЛК (CODESYS)

Код ST в `src/` (раскладка «один объект — один файл», [docs/LAYOUT.md](docs/LAYOUT.md)):

| Объект | Назначение |
|---|---|
| `PRG_Iiot` | обвязка: вызывается из `PRG_Main` (во флагмане — после `PRG_Devices`), связывает ФБ ниже с `GVL_Devices` и `GVL_Hmi` флагмана |
| `FB_MqttTelemetry` | телеметрия по изменению с зоной нечувствительности и периодически, качество по NAMUR NE 107 |
| `FB_MqttAlarms` | события тревог ISA-18.2 по словам тревог устройств, снимок после рождения |
| `FB_MqttCommands` | подписка на команды, белый список и диапазоны (`GVL_IiotMap` — генерируется из `schema/`), ответ `cmd_ack` |
| `FB_MqttDiag` | связь с брокером: повторы с удвоением паузы, завещание (LWT), рождение, счётчики, статус NE 107 |
| `FB_JsonBuilder`, `FB_JsonFlatParser` | JSON без ограничения 255 символов строковых функций CODESYS |
| `I_MqttClient` | транспорт MQTT за интерфейсом; адаптер на CODESYS-MQTT — `adapters/sd_mqtt_1_0/` |

Сборка и тесты — одной командой `python tools/codesys/cds.py build|test` (CODESYS 3.5.17.30 и CODESYS
Control Win V3 в пользовательском процессе, [tools/README.md](tools/README.md)). Установка библиотеки
CODESYS-MQTT и настройка Symbol Configuration для OPC UA-сервера — [docs/MANUAL_STEPS.md](docs/MANUAL_STEPS.md),
разделы 9–10; подробности ПЛК-части — [docs/plc_mqtt.md](docs/plc_mqtt.md).

## Безопасность

Кратко ([docs/security.md](docs/security.md) — полностью, с источниками):

- **Рантайм CODESYS**: обязательное управление пользователями (с SP17), отдельные учётные записи с
  минимальными правами; рантайм стенда 3.5.17.30 подвержен CVE-2023-5751 — на объекте нужна новее.
- **OPC UA**: на объекте только Basic256Sha256 (или Aes) с SignAndEncrypt, вход по пользователю,
  списки доверенных сертификатов с обеих сторон; запись — только в структуры команд.
- **MQTT**: анонимный доступ выключен, четыре роли с ACL (ПЛК, Telegraf, оператор, мониторинг),
  TLS по флагу; команды без retain, белый список и диапазоны проверяет сам ПЛК.
- **Сеть**: зоны и каналы в духе МЭК 62443 (управление, DMZ, предприятие), таблица каналов C1–C7.
- **Секреты** — только в `.env` (в git — `.env.example`, рабочий файл — права 0600), у Telegraf и
  Grafana — свои токены InfluxDB с минимальными правами, Grafana шифрует их своим ключом. Для значимых объектов КИИ — ссылка на требования ФСТЭК России
  (приказ № 239); соответствие им проект не утверждает.

## Тесты и проверки

| Что | Где | Результат |
|---|---|---|
| ruff, `mypy --strict`, pytest: схемы и примеры, каталог против перечня iolistgen, Telegraf, дашборды, compose, генераторы, локальный стенд, точные JSON ПЛК против JSON Schema | CI (`checks`), локально | зелёные локально |
| эмулятор и отчёт: mypy, pytest (модель, шлюз команд, OPC UA и MQTT на 127.0.0.1, сообщения по схеме; агрегаты отчёта) | CI (`packages`), локально | зелёные локально |
| `make demo` с нуля на Linux, интеграционные тесты, панели дашбордов, отчёт по данным стенда | CI (`stack`, docker compose) | проверяется в CI |
| тот же путь «эмулятор → брокер → Telegraf → InfluxDB → Grafana» без Docker | локально, `local_stack.ps1` | 12 интеграционных тестов зелёные; данные есть у всех 42 панелей (списки отклонений пусты, пока всё в норме) |
| `st_lint --strict`, iec_checker v0.4 (`run_iec_checker.py --tests`), RuSTy (необязательно) | CI, локально | st_lint и iec_checker без необоснованных замечаний и ошибок разбора; RuSTy — расширения CODESYS, которых в нём нет; разбор — [docs/STATIC_ANALYSIS.md](docs/STATIC_ANALYSIS.md) |
| сборка и 87 тестов coUnit в CODESYS 3.5.17.30 / Control Win V3 | Windows, `cds.py build`, `cds.py test` | ошибок 0, предупреждений 0; [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |

Интеграционные тесты (`tests_stack/test_stack_integration.py`, маркеры `integration` и `stack`)
пропускаются, если стенд не поднят; с `IIOT_STACK=1` (`make test-stack`, CI) это ошибка. Они проверяют:
все 115 метрик каталога доходят до InfluxDB, путь OPC UA, отказ брокера оператору в публикации
телеметрии, отбрасывание чужой мажорной версии схемы, завещание (LWT) при обрыве связи, аудит команд и
сквозной отказ команды вне белого списка (ответ `not_whitelisted`, запись в базе, счётчик отказов узла,
режим насоса не изменился), часовые агрегаты задачи прореживания против расчёта по сырым точкам.

## Документация

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — сервисы, потоки данных, выбор базы, хранение, сеть, локальный стенд
- [data_schema.md](docs/data_schema.md) — топики, сообщения, белый список команд, модель InfluxDB, версии
- [security.md](docs/security.md) — пользователи рантайма, OPC UA, MQTT, зоны и каналы, КИИ
- [plc_mqtt.md](docs/plc_mqtt.md) — ПЛК-часть: ФБ, проверки команд, адаптер CODESYS-MQTT
- [MANUAL_STEPS.md](docs/MANUAL_STEPS.md) — шаги в IDE: CODESYS-MQTT, Symbol Configuration, встраивание во флагман
- [ASSUMPTIONS.md](docs/ASSUMPTIONS.md) — допущения и решения
- [TEST_REPORT.md](docs/TEST_REPORT.md), [STATIC_ANALYSIS.md](docs/STATIC_ANALYSIS.md) — отчёты
- [emulator/README.md](emulator/README.md), [report/README.md](report/README.md) — эмулятор и отчёт

## Ограничения и дальнейшие шаги

- Библиотека CODESYS-MQTT (релиз `stable`, 1.0.0.0) на CODESYS 3.5.17.30 не собирается: нет её
  зависимостей (OSCAT и системные библиотеки точных версий). Логика MQTT проверена с подменным
  клиентом, адаптер `FB_MqttClientSdMqtt` с библиотекой не компилировался; без адаптера ПЛК-часть
  работает с клиентом без транспорта. Версия 1.0.0.0 не передаёт логин и пароль — к брокеру стенда
  она не подключится.
- Стенд docker compose целиком проверяется в CI на Linux; на машине разработки Docker нет, поэтому
  локально тот же путь проверен на родных сборках Windows (отличия — в ARCHITECTURE.md, раздел 10).
- Эмулятор ускоряет модельное время (`EMU_TIME_FACTOR=60`: сутки за 24 минуты), а метки времени
  остаются реальными: моточасы и пуски на дашбордах и в отчёте растут в 60 раз быстрее, чем расход.
  Для правдоподобного суточного отчёта — `EMU_TIME_FACTOR=1`.
- События тревог ПЛК восстанавливаются по словам тревог устройств; точные события ISA-18.2 даст
  приёмник `PL.I_AlarmSink` plc-process-lib при встраивании во флагман.
- Flux в InfluxDB 2 не развивается: переход на InfluxDB 3 потребует переписать запросы дашбордов и
  отчёта на SQL или InfluxQL (модель хранения переносится без изменений).

## Summary (EN)

An infrastructure-as-code IIoT stand for a (fictional) sewage pumping station: PLC data flows over
MQTT and OPC UA through Telegraf into InfluxDB 2 and three provisioned Grafana dashboards, while
operator commands travel back and are checked in the PLC against a whitelist with value ranges.
`make demo` starts the docker compose stack with a Python PLC emulator (asyncua OPC UA server with
the flagship's real tag model, paho-mqtt publisher) and waits until data is on the dashboards.
Topics follow `site/area/unit/device/metric`, every message carries `schema_version` and is
validated against JSON Schema. The PLC side is CODESYS 3.5.17.30 Structured Text (telemetry,
alarms, command gateway, link diagnostics) with 87 coUnit tests; a daily CSV/XLSX report and a
security guide (IEC 62443 zones, OPC UA policies, MQTT TLS/ACL) are included. Docs are in Russian.

## Лицензия

[MIT](LICENSE) © 2026 <ИМЯ ФАМИЛИЯ>

---

<p align="center"><b>Портфолио АСУ ТП</b></p>
<table>
<tr><td width="33%"><a href="https://github.com/<GITHUB_USER>/plc-repo-template">01 · plc-repo-template</a><br><sub>ST в git, сборка проекта скриптом, CI</sub></td><td width="33%"><a href="https://github.com/<GITHUB_USER>/plc-process-lib">02 · plc-process-lib</a><br><sub>ФБ: AI, двигатель, ПЧ, задвижка, ПИД, тревоги</sub></td><td width="33%"><a href="https://github.com/<GITHUB_USER>/kns-pump-station">03 · kns-pump-station</a><br><sub>флагман: КНС, три насоса с ПЧ, модель, HMI</sub></td></tr>
<tr><td width="33%"><a href="https://github.com/<GITHUB_USER>/kns-port-domestic">04 · kns-port-domestic</a><br><sub>перенос на Astra.IDE / MasterSCADA 4D</sub></td><td width="33%"><a href="https://github.com/<GITHUB_USER>/plc-iiot-stack"><b>05 · plc-iiot-stack</b></a><br><sub>OPC UA / MQTT → InfluxDB → Grafana</sub></td><td width="33%"><a href="https://github.com/<GITHUB_USER>/iolistgen">06 · iolistgen</a><br><sub>перечень сигналов → ST, карты Modbus, SCADA</sub></td></tr>
<tr><td width="33%"><a href="https://github.com/<GITHUB_USER>/plc-ci-toolkit">07 · plc-ci-toolkit</a><br><sub>линтеры, сборка CODESYS, тесты, JUnit</sub></td><td width="33%"><a href="https://github.com/<GITHUB_USER>/s7-to-codesys">08 · s7-to-codesys</a><br><sub>конвертер SCL → ST с отчётом о переносе</sub></td><td width="33%"><a href="https://github.com/<GITHUB_USER>/sis-interlock-demo">09 · sis-interlock-demo</a><br><sub>ПАЗ: MooN, матрица причин и следствий</sub></td></tr>
</table>
