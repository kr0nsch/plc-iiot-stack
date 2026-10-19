# Работа со стендом: эмулятор, Grafana, команды, флагман по OPC UA

Как поднять стенд на эмуляторе ПЛК, где смотреть насосы и тревоги, как отправить команду и как
переключить стенд с эмулятора на флагман КНС-1 в CODESYS. Всё, что ниже помечено «увидите», — вывод
реального прогона на локальном стенде без Docker (Windows 11, 19.10.2026); у docker compose вывод
`make demo` другой, а данные те же.

## Содержание

1. [Что нужно](#1-что-нужно)
2. [Стенд на эмуляторе](#2-стенд-на-эмуляторе)
3. [Grafana: насосы, станция, тревоги](#3-grafana-насосы-станция-тревоги)
4. [Команда](#4-команда)
5. [Стенд против флагмана в CODESYS](#5-стенд-против-флагмана-в-codesys)
6. [Свой объект вместо КНС-1](#6-свой-объект-вместо-кнс-1)
7. [Частые проблемы](#7-частые-проблемы)

## 1. Что нужно

| Путь | Что поставить |
|---|---|
| docker compose (основной, проверяется в CI) | Docker с compose v2, Python 3.11+, `make` (на Windows — `tools_project\make.ps1`) |
| локальный стенд без Docker (Windows) | Python 3.11+ (проверено на 3.12); `local_stack.ps1 install` скачает InfluxDB, Telegraf и Grafana для Windows (SHA-256 сверяется) и поставит брокер amqtt в отдельный venv, права администратора не нужны |

Зависимости проверок и инструментов: `python -m pip install -r requirements-dev.txt`. CODESYS для
стенда не нужен: данные даёт эмулятор `emulator/` с теми же узлами OPC UA и топиками, что у флагмана.

## 2. Стенд на эмуляторе

**docker compose:**

```bash
make demo        # .env со случайными паролями, сборка эмулятора, стенд, ожидание данных (до 300 с)
make test-stack  # интеграционные тесты и проверка панелей дашбордов
make down        # остановка; make clean — с удалением данных
```

**Windows без Docker:**

```powershell
powershell -ExecutionPolicy Bypass -File tools_project\local_stack.ps1 install           # один раз
powershell -ExecutionPolicy Bypass -File tools_project\local_stack.ps1 start -Emulator
```

Увидите (сокращено):

```text
broker готов
influxdb готов
influx-init: готово
telegraf готов
grafana готов
emulator готов
[    5 с] свежих точек LT101/level — 3, PLC1 online — да, дашбордов нет — 0
данные на дашбордах: http://127.0.0.1:3000/d/kns1-overview (логин — GRAFANA_ADMIN_* в .env)
```

Проверить путь данных целиком — `python -m pytest -m stack tests_stack` (увидите `14 passed`):
все 139 метрик каталога по MQTT и все 133 узла OPC UA, ACL брокера, отказ команды вне белого списка,
команда станции, агрегаты задачи прореживания. Остановка — `local_stack.ps1 stop` (`-Clean` удалит и
данные).

Эмулятор ускоряет модельное время в 60 раз (`EMU_TIME_FACTOR` в `.env`): сутки станции — за 24 минуты.
Автоматический сценарий отказов по зерну даёт тревоги в первые минуты (дверь павильона, сероводород,
авария ПЧ, потеря связи с ПЧ) — на дашборде тревог есть что смотреть без ручных действий.

## 3. Grafana: насосы, станция, тревоги

http://localhost:3000 (docker compose) или http://127.0.0.1:3000, логин и пароль — `GRAFANA_ADMIN_USER`,
`GRAFANA_ADMIN_PASSWORD` в `.env`. Три дашборда (генерирует `tools_project/gen_config.py`, правки в
интерфейсе не сохраняются):

| Дашборд | Что на нём |
|---|---|
| «КНС-1: обзор станции» | уровень LT101 на фоне уставок LL…HH, насосы P101–P103 (состояние, скорость, режим, NE 107), общая авария K1, связь с ПЛК и возраст данных, коллектор (давление, расход), электроснабжение, газоанализ, активные тревоги |
| «Насосы: моточасы и пуски» | наработка и пуски за период и по суткам, пуски за скользящий час, ток двигателей, состояние насосов, счётчики до ТО |
| «Тревоги за период» | срабатывания по часам и приоритетам (ISA-18.2), топ-10, текущее состояние каждой тревоги и журнал событий — в том числе тревоги станции `KNS1.*` |

Переменная «Источник» вверху: `mqtt` — значения, которые публикует ПЛК (эмулятор), `opcua` — те же
метрики, прочитанные Telegraf с OPC UA-сервера. Метрики станции и регулятора уровня (`KNS1/*`,
`LIC101/*`: режим, способ, действующее управление, число насосов, ведущий, задания) есть в базе
(measurement `telemetry`, [data_schema.md, 3.4](data_schema.md#34-каталог-метрик)); на трёх дашбордах
их отдельных панелей пока нет — смотреть в Explore или Data Explorer InfluxDB.

## 4. Команда

Команда оператора — сообщение в `vodokanal/kns1/station/<device>/cmd/<command>`; ПЛК (или эмулятор)
проверяет её по порядку контракта и отвечает в `…/cmd_ack/<command>`
([data_schema.md, раздел 5](data_schema.md#5-команды)). Из командной строки:

```bash
python tools_project/send_command.py P103 SpeedSp 70
```

Увидите:

```text
→ P103/cmd/SpeedSp {"schema_version": "1.1", "cmd_id": "80cf…254e", "ts": 1792433564074, "origin": "operator@send_command", "command": "SpeedSp", "value": 70.0}
← P103/cmd_ack/SpeedSp {"schema_version": "1.1", "cmd_id": "80cf…254e", "ts": 1792433564720, "command": "SpeedSp", "result": "accepted", "reason": "ok"}
```

| Пример | Что будет |
|---|---|
| `python tools_project/send_command.py KNS1 SetStepped` | станция переходит на ступенчатое регулирование: `accepted`, `cmd_result` `Accepted`; обратно — `KNS1 SetLevelPid` |
| `python tools_project/send_command.py P102 SetManual` | насос P102 в ручной режим; `P102 Start`, `P102 Stop` — пуск и останов с «пульта», `P102 SetAuto` — обратно в автомат |
| `python tools_project/send_command.py LT101 Ack` | квитирование тревог уровнемера |
| `python tools_project/send_command.py P101 SetOos` | вывод из работы по MQTT запрещён: `rejected`, `reason` `not_whitelisted` (инструмент предупредит заранее, но отправит — так видно проверку в ПЛК) |
| `python tools_project/send_command.py P103 SpeedSp 140` | вне 0…100 %: инструмент предупредит, что команда не по схеме; ответ `rejected`, `reason` `out_of_range` |

Код выхода: 0 — `accepted`, 1 — `rejected`, 2 — нет ответа (ПЛК или эмулятор не подключён к брокеру).
Пользователь — `MQTT_OPERATOR_USER` из `.env`: ACL брокера разрешает ему публиковать только команды.
Белый список — `schema/command_whitelist.csv`; ответ и журнал аудита пишутся в InfluxDB (measurement
`command`, `command_ack`).

## 5. Стенд против флагмана в CODESYS

Флагман kns-pump-station работает в CODESYS Control Win V3 как приложение имитации; его OPC UA-сервер
отдаёт те же узлы, что эмулятор (`ns=4;s=|var|CODESYS Control Win V3.Application.GVL_…`). Путь OPC UA
работает без изменений во флагмане:

1. Во флагмане: `python tools_project/codesys/sim.py start` (импорт, символы, рантайм, сертификат
   OPC UA-сервера, загрузка и «Старт»).
2. Адрес и вход — в `.env` стенда или в переменных окружения запуска (они важнее `.env`, поэтому пароль
   пользователя рантайма в файл писать не обязательно):

   ```ini
   OPCUA_ENDPOINT=opc.tcp://host.docker.internal:4840     # без Docker: opc.tcp://127.0.0.1:4840
   OPCUA_SECURITY_POLICY=Basic256Sha256
   OPCUA_SECURITY_MODE=SignAndEncrypt
   OPCUA_AUTH_METHOD=UserName
   OPCUA_USERNAME=<пользователь рантайма с правом чтения>
   OPCUA_PASSWORD=<его пароль>
   ```

3. Стенд без эмулятора: `make up` или `local_stack.ps1 start` (без `-Emulator`).
4. Сертификат Telegraf — в доверенные рантайма (первое подключение сервер отклоняет, сертификат — в
   карантине `.pki`), перезапуск рантайма с приложением (`sim.py start --no-import --restart-runtime`).
5. Проверка: `python tools_project/opcua_live_check.py` (вход, пространство имён, префикс, 133 узла, типы,
   K1; с `--commands` — ещё команды станции и LIC101); Grafana, «Источник» = `opcua`.

Подробно — [MANUAL_STEPS.md, раздел 12](MANUAL_STEPS.md#12-стенд-против-флагмана-в-codesys-opc-ua); так
проверено 19.10.2026: 133 узла из 133 со статусом Good в InfluxDB. Встраивание ПЛК-части во флагман —
`python tools_project/flagship_embed.py --repo <рабочая копия флагмана>`
([MANUAL_STEPS.md, раздел 11](MANUAL_STEPS.md#11-встраивание-во-флагман)). Путь MQTT (публикация из ПЛК,
тревоги, команды) появится после подключения библиотеки MQTT (раздел 9 там же).

## 6. Свой объект вместо КНС-1

Контракт стенда — файлы `schema/`; всё остальное из них генерируется или проверяется по ним.

| Шаг | Команда или файл |
|---|---|
| 1. Теги и тревоги объекта | свой перечень сигналов → `scada_tags.csv`, `scada_alarms.csv` (генератор iolistgen) в `schema/source/`; для флагмана — `python tools_project/flagship_snapshot.py` |
| 2. Метрики | `schema/telemetry_catalog.csv`: устройство, имя метрики, тег, вид, единица, зона нечувствительности, путь в ПЛК |
| 3. Команды | `schema/command_whitelist.csv`: что разрешено по MQTT и с каким диапазоном |
| 4. Топики | `schema/topics.json`, раздел `station`: `site`, `area`, `unit`, узел ПЛК |
| 5. Генерация | `python tools_project/gen_config.py` (узлы OPC UA Telegraf, тексты тревог, дашборды, таблицы схемы), `python tools_project/gen_plc_iiot.py` (таблицы и привязка ST) |
| 6. Проверка | `python -m pytest` — каталог против тегов, схемы, Telegraf, дашборды; с флагманом — и пути по его символам |
| 7. Копии в пакетах | те же CSV и `topics.json` — в `emulator/iiot_emulator/data/` (тест сверяет побайтно) |

Эмулятор написан под КНС-1 (модель резервуара и насосов, логика станции): для другого объекта его
модель придётся заменить, а узлы OPC UA и топики он берёт из тех же файлов.

## 7. Частые проблемы

| Что видно | Причина и что сделать |
|---|---|
| `make demo` или `start -Emulator` ждёт данные дольше 5 минут | Telegraf не подключился к брокеру или InfluxDB: `docker compose logs telegraf` или `local_stack.ps1 logs` |
| `send_command.py`: «нет ответа cmd_ack» | эмулятор (или ПЛК) не подключён к брокеру; узел PLC1 на дашборде обзора — «нет связи» |
| дашборды пустые при «Источник» = `opcua` | Telegraf не читает OPC UA: адрес `OPCUA_ENDPOINT`, политика и доверие сертификату (раздел 5) |
| на Windows порт 4840 занят | это OPC UA-сервер службы CODESYS Control Win; локальный стенд даёт эмулятору порт 4841 |
| `local_stack.ps1`: порт 8080 Telegraf занят | другой адрес проверки здоровья: `$env:LOCAL_TELEGRAF_HEALTH_PORT = '8089'` перед `start` |
