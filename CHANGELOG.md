# Changelog

Все заметные изменения проекта записываются в этот файл.

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версии — по
[Semantic Versioning](https://semver.org/lang/ru/spec/v2.0.0.html). Версия схемы данных
(`schema_version` в сообщениях) ведётся отдельно — [docs/data_schema.md](docs/data_schema.md), раздел 8.

## [Unreleased]

Проект создан из шаблона plc-repo-template: инструменты `tools/` (сборка ST, линтер, iec_checker,
RuSTy, `cds.py` для CODESYS 3.5.17.30) — из шаблона, пример шаблона в `src/` и `tests/` заменён кодом
проекта.

### Added

- Схема данных 1.0: топики `site/area/unit/device/metric`, JSON Schema 2020-12 для телеметрии, тревог,
  команд, ответов и состояния узла (`schema/*.schema.json`), каталог метрик и белый список команд по
  перечню сигналов флагмана (iolistgen), примеры сообщений, модель хранения InfluxDB
  ([docs/data_schema.md](docs/data_schema.md)).
- Стенд docker compose: Mosquitto 2.0 (пароли и ACL из `.env`, TLS по флагу), InfluxDB 2.9
  (бакеты сырых данных и агрегатов, задача прореживания, токены с минимальными правами), Telegraf 1.39
  (пять входов MQTT и вход OPC UA на 115 узлов, тексты тревог по коду), Grafana 12.4 (провиженинг
  источника и трёх дашбордов: обзор станции, насосы — моточасы и пуски, тревоги за период), Node-RED
  по желанию; `make up | demo | down | clean | test | test-stack | certs | gen`, то же —
  `tools_project/make.ps1` для Windows.
- Эмулятор ПЛК `emulator/` (`kns-emulator`): OPC UA-сервер на asyncua с тегами и узлами флагмана,
  модель КНС (приток, насосы, станционная логика, 31 отказ и сценарий по зерну), публикатор MQTT и
  шлюз команд по контракту.
- Сторона ПЛК (ST, CODESYS 3.5.17.30): `PRG_Iiot`, `FB_MqttTelemetry`, `FB_MqttAlarms`,
  `FB_MqttCommands`, `FB_MqttDiag`, `FB_JsonBuilder`, `FB_JsonFlatParser`, функции `F_Iiot*`,
  интерфейс `I_MqttClient`; таблицы метрик, команд и тревог генерируются из `schema/`
  (`tools_project/gen_plc_iiot.py`); заглушка имён флагмана `KnsShim`; адаптер на CODESYS-MQTT 1.0.0.0
  вне `src/` (`adapters/sd_mqtt_1_0/`). 87 тестов coUnit — зелёные в CODESYS Control Win V3.
- Суточный отчёт `report/` (`kns-report`): InfluxDB (Flux) или OPC UA → CSV и XLSX.
- [docs/security.md](docs/security.md): пользователи и права рантайма CODESYS, политики OPC UA и
  сертификаты, TLS и ACL MQTT, зоны и каналы в духе МЭК 62443, ссылка на требования ФСТЭК России
  (приказ № 239) для значимых объектов КИИ.
- Локальный стенд без Docker: `tools_project/local_stack.ps1` (install, start, stop, status, logs) и
  `tools_project/local_stack.py` — официальные сборки InfluxDB, Telegraf и Grafana для Windows тех же
  версий (SHA-256 сверяется), брокер amqtt, конфигурация из `docker-compose.yml` с адресами и путями
  хоста ([docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), раздел 10).
- `tools_project/check_dashboards.py`: каждая панель трёх дашбордов возвращает данные (запросы
  выполняет Grafana, `POST /api/ds/query`); входит в `make test-stack`.
- Интеграционные тесты `tests_stack/test_stack_integration.py` (маркеры `integration` и `stack`,
  пропуск без поднятого стенда): все метрики каталога в InfluxDB по MQTT, путь OPC UA, ACL брокера,
  фильтр мажорной версии схемы, аудит команд, сквозной отказ команды вне белого списка и вне диапазона,
  принятая команда; работают и с compose (HTTP API или influx CLI в контейнере), и с локальным стендом.
- Тесты согласованности: точные JSON, которые ST формирует в тестах coUnit, проходят JSON Schema своего
  класса; локальный стенд повторяет пользователей, ACL, переменные и тома compose.
- CI `.github/workflows/ci.yml`: задания шаблона (ruff, mypy, pytest, сборка ST, st_lint, iec_checker,
  RuSTy), `packages` — mypy и pytest эмулятора и отчёта, `stack` — `make demo DEV=1` с нуля на Linux,
  `make test-stack` и отчёт по данным стенда (заменяет отдельный `stack.yml`).
- Медиа README в `docs/media/`: баннеры для тёмной и светлой темы, social preview, GIF дашборда обзора
  и снимки трёх дашбордов Grafana с локального стенда, GIF запуска стенда с интеграционными тестами и
  прогона `cds.py test` в CODESYS 3.5.17.30 — всё с реальных прогонов; шапка README, раздел
  «Демонстрация» и подвал со ссылками на репозитории портфолио.

### Changed

- Статанализ ST — `tools/check/run_iec_checker.py --tests` шаблона (локально, обязательное задание CI и
  необязательное `nightly`): после обновления `tools/` из plc-repo-template понижение варианта сборки
  `iec-checker` разбирает все конструкции проекта — ошибок разбора 0 (прямой запуск раньше давал 41).
  Обёртка `tools_project/iec_checker_gate.py`, её список пробелов разборщика
  `tools_project/iec_checker_parser_gaps.toml` и тест `tests_stack/test_iec_checker_gate.py` удалены,
  исключение шаблонного `test_integration_repository_sources` из `pyproject.toml` убрано.
- `tools/check/iec_checker_allow.toml`: ложные UnusedVariable (обращения из методов, через вызов, метод
  или поле, в границе `FOR`) — записи по объектам с перечнем имён; что к каждому имени есть обращение,
  проверяет `tests_stack/test_iec_checker_allow.py`. Обоснование OutOfBounds для `FB_IiotKnsMap` удалено:
  понижение шаблона `a[i].x` таких находок больше не даёт ([docs/STATIC_ANALYSIS.md](docs/STATIC_ANALYSIS.md)).
- Тест coUnit `IntExtremes`: границы LINT записаны шестнадцатеричными литералами — набор
  `FB_JsonBuilder_Test` теперь проходит статанализ (десятичный литерал больше 2^62 - 1 iec_checker 0.4
  не читает).
- RuSTy (`run_rusty.py`, необязательно): 314 ошибок вместо 414 — `VAR_IN_OUT CONSTANT` (100 ошибок E034
  и E036) теперь заменяет вариант сборки `rusty` шаблона; оставшиеся — расширения CODESYS, которых нет в
  RuSTy и в прокладках шаблона.

### Fixed

- Эмулятор: зона нечувствительности — строгое «больше», как в контракте и `F_IiotDeadbandExceeded`
  (было `>=`).
- Дашборд «Тревоги за период», «Топ-10 тревог»: тревоги без срабатываний (счётчик 0) больше не
  попадают в топ.
- `docs/data_schema.md`: шаг 2 проверки команды — состав полей и типы, диапазон значения — шаг 6
  (`out_of_range`), как в ПЛК и эмуляторе; пример `opcua_status` — в формате Telegraf 1.39.
- Telegraf, `node_status`: время точки — время приёма, а не `ts`. У завещания `ts` — время подключения,
  точка `offline` ложилась раньше рождения того же подключения, и после обрыва связи панель «Связь с
  ПЛК» и ожидание `make demo` продолжали считать узел в сети (найдено на локальном стенде).
- Дашборды «Обзор станции» и «Насосы», панели состояния насосов: цвет — фиксированный, а не по порогам;
  с порогами и `mergeValues` Grafana показывала одну полосу «-∞+» вместо «Работа / Стоп / Отказ».
- Telegraf: явное `skip_processors_after_aggregators` (предупреждение о смене умолчания в 1.40).
- Тесты отчёта не зависят от переменных стенда в окружении (`INFLUX_*` из загруженного `.env`), кроме
  теста с маркером `integration`.
- ПЛК, `FB_MqttAlarms`: после каждого переподключения активная неквитированная тревога уходила снимком
  с новым `ts` и `reason = Activated` — дашборды («Срабатываний за период», «Топ-10», журнал) и
  суточный отчёт считали её новым срабатыванием при каждом обрыве связи (у квитированной — ложное
  `Acked`). Теперь не менявшаяся тревога повторяется последней публикацией с исходными `ts` и
  `prev_state` (в InfluxDB — та же точка), переход без связи — событие с текущим `ts`; тесты
  `ReconnectRepeatsLastEventWithItsTs`, `ChangeWhileOfflineIsEventAfterReconnect`.
- ПЛК, `FB_MqttTelemetry`: неконечное значение (NaN, ±Inf) уходило как `"value": null` — нарушение
  `telemetry.schema.json`; теперь — последнее опубликованное конечное значение с `quality = bad`
  (data_schema 3.2), тест `NotFiniteValueSendsLastFiniteAsBad`.
- Задача `kns_downsample_1h`: `mean` было простым средним по точкам — для публикации по изменению
  оно смещено (на данных стенда 1,27 м против 1,21 м); теперь среднее, взвешенное по времени
  (удержание до 10 мин, как в отчёте), без `quality = bad`, `min`/`max` — по действовавшим значениям.
  `influxdb-init` (и локальный стенд) обновляет текст уже созданной задачи, а не только создаёт её.
- Telegraf, вход OPC UA: сертификат клиента не задавался — с защищённой политикой Telegraf брал путь по
  умолчанию `/etc/telegraf/cert.pem` в слое контейнера (без постоянного тома), и после пересоздания
  контейнера серверу CODESYS пришлось бы заново доверять новому сертификату. Теперь `OPCUA_CERTIFICATE`/`OPCUA_PRIVATE_KEY`,
  по умолчанию — том `telegraf-pki`: сертификат создаётся один раз.
- Безопасность: `.env` создаётся с правами 0600 (было 0644 по umask); Grafana шифрует секреты своим
  ключом `GRAFANA_SECRET_KEY` вместо общего ключа по умолчанию; слушатель MQTT TLS — явный минимум
  `tls_version tlsv1.2`.
- Дашборды: шкала времени — в поясе станции (Europe/Moscow), как границы суток в запросах и отчёт; с
  поясом браузера суточные столбцы у зрителя в другом поясе были сдвинуты относительно шкалы.
- Образ эмулятора: в `docker/emulator-constraints.txt` закреплены и транзитивные зависимости (было —
  только прямые), тест сверяет набор с проверенным; CI предупреждает, если `make demo` с нуля дольше 5 минут.
- Ожидание данных (`make demo`, `local_stack.ps1 start -Emulator`) засчитывало точки прошлого запуска
  из тома InfluxDB; теперь — только с отметкой времени после начала ожидания.
- Документация: Node-RED описан как пустой редактор (готового потока нет), `docs/security.md` — проверки
  возраста, повтора и частоты команд реализованы в ST (было «сверить»), предупреждение о полном
  `telegraf --test` на работающем стенде (перехват постоянных сессий MQTT).
