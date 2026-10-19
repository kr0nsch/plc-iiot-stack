# Схема данных стенда: топики MQTT, сообщения, хранение

Версия схемы: **1.1**. Документ — контракт между ПЛК (сторона ST, `src/` и `flagship/src/`), эмулятором, брокером,
Telegraf, InfluxDB, Grafana и отчётом. Машиночитаемая часть лежит в `schema/`:

| Файл | Что задаёт |
|---|---|
| `schema/topics.json` | грамматика топиков, подписки по классам, QoS и retain, параметры станции |
| `schema/telemetry.schema.json` | телеметрия: одно значение метрики |
| `schema/alarm.schema.json` | событие тревоги (переход состояния) |
| `schema/command.schema.json` | команда устройству |
| `schema/command_ack.schema.json` | ответ на команду |
| `schema/status.schema.json` | состояние узла: рождение, завещание (LWT), штатное отключение |
| `schema/telemetry_catalog.csv` | каталог метрик: устройство, метрика, вид, единицы, зона нечувствительности, путь в ПЛК |
| `schema/command_whitelist.csv` | белый список команд MQTT с диапазонами значений |
| `schema/examples/*.json` | примеры сообщений: `{topic, qos, retain, payload}` |
| `schema/source/scada_tags.csv`, `scada_alarms.csv` | теги и тревоги устройств флагмана — выход генератора iolistgen флагмана, вручную не правится |
| `schema/source/station_tags.csv`, `station_alarms.csv` | теги станции KNS1 и регулятора LIC101 (`GVL_Station`) и тревоги станции `KNS1.*` в том же формате |
| `schema/source/flagship_symbols.json` | снимок интерфейса флагмана: коммит, объявления глобальных списков, типы, правила символьной конфигурации OPC UA |

Тесты `tests_stack/` проверяют, что схемы корректны, примеры им соответствуют, а Telegraf, дашборды
и каталог ссылаются только на объявленные здесь имена.

## 1. Объект и источники имён

Данные — вымышленной КНС-1 (флагман портфолио, проект 02): резервуар с уровнемером LT101, три насоса
с ПЧ P101–P103, коллектор с PT201 и FT202, вспомогательные системы. Имена устройств — позиции по
перечню сигналов (`schema/source/scada_tags.csv`): экземпляры `GVL_Devices.fb<DEV>` и команды
`GVL_Hmi.st<DEV>Cmd` библиотеки plc-process-lib. Схема данных не вводит своих имён устройств: только
имена метрик (раздел 3) и классы сообщений.

Кроме устройств перечня в схеме есть станция `KNS1` (состояние `GVL_Station.stStationSts`, команды
`stStationCmd`) и регулятор уровня `LIC101` (`GVL_Station.fbLIC101`, команды `stLIC101Cmd`) — имена
флагмана (DESIGN 3.1 и 4.1 kns-pump-station). Все пути, их типы и права записи по OPC UA сверены со
снимком интерфейса флагмана (`schema/source/flagship_symbols.json`, `tools_project/flagship_snapshot.py`):
по MQTT и OPC UA пишутся только структуры команд.

## 2. Топики

### 2.1 Соглашение

```
{site}/{area}/{unit}/{device}/{metric}            телеметрия: 5 уровней
{site}/{area}/{unit}/{device}/{class}/{name}      прочие классы: 6 уровней
```

| Уровень | Правило | КНС-1 |
|---|---|---|
| `site` | `[a-z][a-z0-9_]{0,31}` — предприятие | `vodokanal` |
| `area` | то же — площадка, объект | `kns1` |
| `unit` | то же — технологическая установка | `station` (на КНС одна установка) |
| `device` | `[A-Z][A-Z0-9_]{0,15}` — позиция по перечню | `LT101`, `P101`, `K1`; станция — `KNS1`, регулятор — `LIC101`; узел ПЛК — `PLC1` |
| `metric` | `[a-z][a-z0-9_]{0,31}` — имя метрики из каталога | `level`, `running`, `run_hours` |

Пример: `vodokanal/kns1/station/LT101/level` — уровень в приёмном резервуаре.

Телеметрия занимает ровно пять уровней, остальные классы — шесть. Поэтому подписка
`vodokanal/+/+/+/+` получает только телеметрию, а у каждого класса своя подписка без пересечений:
у брокера и Telegraf нет фильтрации «по содержимому». Имена `alarm`, `cmd`, `cmd_ack`, `status`
зарезервированы и метриками быть не могут.

### 2.2 Классы сообщений

| Класс | Топик | Кто публикует | QoS | retain | Схема |
|---|---|---|---|---|---|
| телеметрия | `{site}/{area}/{unit}/{device}/{metric}` | ПЛК (эмулятор) | 1 | да | `telemetry.schema.json` |
| тревога | `{site}/{area}/{unit}/{device}/alarm/{suffix}` | ПЛК | 1 | да | `alarm.schema.json` |
| команда | `{site}/{area}/{unit}/{device}/cmd/{command}` | оператор: HMI, Node-RED, SCADA | 1 | **нет** | `command.schema.json` |
| ответ на команду | `{site}/{area}/{unit}/{device}/cmd_ack/{command}` | ПЛК | 1 | нет | `command_ack.schema.json` |
| состояние узла | `{site}/{area}/{unit}/{node}/status/connection` | ПЛК; LWT — брокер | 1 | да | `status.schema.json` |

- `retain` у телеметрии и тревог: новый подписчик (HMI, Telegraf после перезапуска) сразу получает
  последнее значение и текущее состояние тревоги. Свежесть значения подписчик оценивает по `ts` и по
  состоянию узла (`status/connection`).
- Команда никогда не публикуется с `retain`: иначе брокер повторит её при каждом переподключении ПЛК.
  ПЛК отклоняет команду с флагом retain (`reason = retained`).
- QoS 1 и постоянная сессия Telegraf: пока Telegraf перезапускается, брокер копит сообщения
  (`max_queued_messages` в `mosquitto/config/mosquitto.conf`). Повторная доставка безопасна: точка
  с теми же тегами и временем в InfluxDB перезаписывается, а не дублируется.

### 2.3 Права (ACL брокера)

| Пользователь (`.env`) | Роль | Публикует | Подписывается |
|---|---|---|---|
| `MQTT_PLC_USER` | ПЛК или эмулятор | телеметрия, `alarm`, `cmd_ack`, `status` | `cmd` |
| `MQTT_TELEGRAF_USER` | сбор в БД | — | всё под `vodokanal/` (команды — для журнала аудита) |
| `MQTT_OPERATOR_USER` | HMI, Node-RED, тесты | `cmd` | всё под `vodokanal/` |
| `MQTT_MONITOR_USER` | проверка здоровья брокера | — | `$SYS/#` |

Анонимный доступ выключен. Файл ACL — `mosquitto/config/acl.template` (имена пользователей
подставляются из `.env` при старте контейнера).

## 3. Телеметрия

### 3.1 Сообщение

```json
{"schema_version": "1.1", "ts": 1792137600250, "value": 2.31, "quality": "good", "unit": "m"}
```

| Поле | Тип | Обязательно | Смысл |
|---|---|---|---|
| `schema_version` | строка `1.x` | да | версия схемы (раздел 8) |
| `ts` | целое | да | время значения в ПЛК, мс от 1970-01-01 UTC. Целое число мс проще всего сформировать в ST (`SysTimeRtcHighResGet`) и однозначно разобрать в Telegraf (`unix_ms`) |
| `value` | число | да | значение в единицах каталога. Дискретное — `0`/`1`, перечисление — код, счётчик — целое. Логических `true`/`false` нет: в InfluxDB поле `value` одного типа (float) во всех рядах |
| `quality` | `good` / `uncertain` / `bad` | да | достоверность (3.2) |
| `unit` | строка | нет | единица из каталога, только для человека; Telegraf её не хранит |

Неизвестные поля получатель игнорирует (правило совместимости MINOR, раздел 8).

### 3.2 Достоверность

`quality` выводится из диагностики устройства-источника (plc-process-lib, NAMUR NE 107):

| Состояние источника | `quality` |
|---|---|
| `eNe107` = Good или MaintenanceRequired, значение достоверно (`xValid`) | `good` |
| `eNe107` = CheckFunction (подмена, вывод из работы, ошибка конфигурации) или OutOfSpecification | `uncertain` |
| `eNe107` = Failure, `xValid = FALSE`, нет связи с ПЧ (для метрик ПЧ) | `bad` |

При `bad` значение всё равно передаётся (последнее достоверное или значение отказа по настройке
`eFailValue` устройства): `value` обязателен.

### 3.3 Публикация

- По изменению: аналоговая метрика — когда значение ушло от последнего опубликованного больше
  зоны нечувствительности (`deadband` каталога); дискретные, перечисления и счётчики — при любом
  изменении (наработка `run_hours` — с шагом 0,01 ч).
- Контрольная публикация всех метрик — раз в `period_ms` (по умолчанию 60 000 мс, объявляется
  в сообщении рождения). Пропуск длиннее трёх периодов дашборды показывают разрывом линии.
- Не чаще одного сообщения в секунду на метрику; изменение `quality` публикуется сразу.

### 3.4 Каталог метрик

Виды: `analog` — измерение (REAL); `discrete` — состояние 0/1; `enum` — код перечисления
(режим 1 Auto, 2 Manual, 3 Local, 4 OutOfService; NE 107 0 Good … 4 Failure; состояние двигателя
0 стоп, 1 пуск, 2 работа, 3 останов, 4 отказ); `counter` — накопительный счётчик; `integer` —
целое, которое может убывать. Единицы — ASCII (`m3/h`, `degC`, `%LEL`), подписи на русском —
в дашбордах. Метрики `PLC1/*` — диагностика связи шлюза MQTT в ПЛК (сторона ST); пути в ПЛК у них
задаёт приложение, а не перечень. Метрики `KNS1/*` и `LIC101/*` — состояние станции и регулятора уровня
флагмана; качество у метрик станции всегда `good` (это расчётные значения логики, а не измерения), у
LIC101 — по его NE 107.

Колонка `invert` каталога: `1` — значение метрики обратно сигналу ПЛК. Так у `K1/general_alarm`: реле
«Общая авария» K1 во флагмане в норме под напряжением (`GVL_IO.xK1 = TRUE`), а метрика — «общая авария»
(1 — авария). ПЛК и эмулятор публикуют по MQTT уже инвертированное значение, путь OPC UA читает `xK1`
как есть и инвертирует его в Telegraf (`processors.starlark` в `telegraf/telegraf.d/opcua.conf`).

<!-- BEGIN GENERATED: telemetry-catalog -->
| Устройство | Метрика | Вид | Ед. | Зона нечувств. | Диапазон | Тег SCADA | Описание |
|---|---|---|---|---|---|---|---|
| `P101` | `running` | discrete |  |  |  | `P101.Running` | Насос Н1: работает |
| `P101` | `state` | enum |  |  |  | `P101.State` | Насос Н1: состояние: 0 стоп, 1 пуск, 2 работа, 3 останов, 4 отказ |
| `P101` | `speed` | analog | % | 0.5 |  | `P101.SpeedAct` | Насос Н1: фактическая скорость |
| `P101` | `speed_ref` | analog | % | 0.5 |  | `P101.SpeedRef` | Насос Н1: задание на ПЧ после ограничений и рампы |
| `P101` | `run_hours` | counter | h | 0.01 |  | `P101.RunTime` | Насос Н1: наработка всего |
| `P101` | `starts` | counter |  |  |  | `P101.Starts` | Насос Н1: пусков всего |
| `P101` | `starts_last_hour` | integer |  |  |  | `P101.StartsLastHour` | Насос Н1: пусков за скользящий час |
| `P101` | `run_hours_maint` | counter | h | 0.01 |  | `P101.RunTimeMaint` | Насос Н1: наработка с последнего ТО |
| `P101` | `starts_maint` | counter |  |  |  | `P101.StartsMaint` | Насос Н1: пусков с последнего ТО |
| `P101` | `vfd_fault_code` | enum |  |  |  | `P101_FCODE` | Насос Н1: код последней аварии ПЧ (читает адаптер ПЧ) |
| `P101` | `mode` | enum |  |  |  | `P101.Mode` | Насос Н1: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `P101` | `ne107` | enum |  |  |  | `P101.Ne107` | Насос Н1: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `P102` | `running` | discrete |  |  |  | `P102.Running` | Насос Н2: работает |
| `P102` | `state` | enum |  |  |  | `P102.State` | Насос Н2: состояние: 0 стоп, 1 пуск, 2 работа, 3 останов, 4 отказ |
| `P102` | `speed` | analog | % | 0.5 |  | `P102.SpeedAct` | Насос Н2: фактическая скорость |
| `P102` | `speed_ref` | analog | % | 0.5 |  | `P102.SpeedRef` | Насос Н2: задание на ПЧ после ограничений и рампы |
| `P102` | `run_hours` | counter | h | 0.01 |  | `P102.RunTime` | Насос Н2: наработка всего |
| `P102` | `starts` | counter |  |  |  | `P102.Starts` | Насос Н2: пусков всего |
| `P102` | `starts_last_hour` | integer |  |  |  | `P102.StartsLastHour` | Насос Н2: пусков за скользящий час |
| `P102` | `run_hours_maint` | counter | h | 0.01 |  | `P102.RunTimeMaint` | Насос Н2: наработка с последнего ТО |
| `P102` | `starts_maint` | counter |  |  |  | `P102.StartsMaint` | Насос Н2: пусков с последнего ТО |
| `P102` | `vfd_fault_code` | enum |  |  |  | `P102_FCODE` | Насос Н2: код последней аварии ПЧ (читает адаптер ПЧ) |
| `P102` | `mode` | enum |  |  |  | `P102.Mode` | Насос Н2: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `P102` | `ne107` | enum |  |  |  | `P102.Ne107` | Насос Н2: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `P103` | `running` | discrete |  |  |  | `P103.Running` | Насос Н3: работает |
| `P103` | `state` | enum |  |  |  | `P103.State` | Насос Н3: состояние: 0 стоп, 1 пуск, 2 работа, 3 останов, 4 отказ |
| `P103` | `speed` | analog | % | 0.5 |  | `P103.SpeedAct` | Насос Н3: фактическая скорость |
| `P103` | `speed_ref` | analog | % | 0.5 |  | `P103.SpeedRef` | Насос Н3: задание на ПЧ после ограничений и рампы |
| `P103` | `run_hours` | counter | h | 0.01 |  | `P103.RunTime` | Насос Н3: наработка всего |
| `P103` | `starts` | counter |  |  |  | `P103.Starts` | Насос Н3: пусков всего |
| `P103` | `starts_last_hour` | integer |  |  |  | `P103.StartsLastHour` | Насос Н3: пусков за скользящий час |
| `P103` | `run_hours_maint` | counter | h | 0.01 |  | `P103.RunTimeMaint` | Насос Н3: наработка с последнего ТО |
| `P103` | `starts_maint` | counter |  |  |  | `P103.StartsMaint` | Насос Н3: пусков с последнего ТО |
| `P103` | `vfd_fault_code` | enum |  |  |  | `P103_FCODE` | Насос Н3: код последней аварии ПЧ (читает адаптер ПЧ) |
| `P103` | `mode` | enum |  |  |  | `P103.Mode` | Насос Н3: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `P103` | `ne107` | enum |  |  |  | `P103.Ne107` | Насос Н3: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `V1` | `running` | discrete |  |  |  | `V1.Running` | Вытяжной вентилятор В1 павильона: работает |
| `V1` | `state` | enum |  |  |  | `V1.State` | Вытяжной вентилятор В1 павильона: состояние: 0 стоп, 1 пуск, 2 работа, 3 останов, 4 отказ |
| `V1` | `run_hours` | counter | h | 0.01 |  | `V1.RunTime` | Вытяжной вентилятор В1 павильона: наработка всего |
| `V1` | `starts` | counter |  |  |  | `V1.Starts` | Вытяжной вентилятор В1 павильона: пусков всего |
| `V1` | `starts_last_hour` | integer |  |  |  | `V1.StartsLastHour` | Вытяжной вентилятор В1 павильона: пусков за скользящий час |
| `V1` | `run_hours_maint` | counter | h | 0.01 |  | `V1.RunTimeMaint` | Вытяжной вентилятор В1 павильона: наработка с последнего ТО |
| `V1` | `starts_maint` | counter |  |  |  | `V1.StartsMaint` | Вытяжной вентилятор В1 павильона: пусков с последнего ТО |
| `V1` | `mode` | enum |  |  |  | `V1.Mode` | Вытяжной вентилятор В1 павильона: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `V1` | `ne107` | enum |  |  |  | `V1.Ne107` | Вытяжной вентилятор В1 павильона: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `LT101` | `level` | analog | m | 0.01 | 0…5 | `LT101.Value` | Уровень в приёмном резервуаре: итоговое значение |
| `LT101` | `mode` | enum |  |  |  | `LT101.Mode` | Уровень в приёмном резервуаре: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `LT101` | `ne107` | enum |  |  |  | `LT101.Ne107` | Уровень в приёмном резервуаре: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `LS102` | `level_high` | discrete |  |  |  | `LS102.Value` | Поплавок «аварийно высокий уровень» (H, 4,2 м): значение для логики |
| `LS102` | `mode` | enum |  |  |  | `LS102.Mode` | Поплавок «аварийно высокий уровень» (H, 4,2 м): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `LS102` | `ne107` | enum |  |  |  | `LS102.Ne107` | Поплавок «аварийно высокий уровень» (H, 4,2 м): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `LS103` | `dry_run` | discrete |  |  |  | `LS103.Value` | Поплавок «сухой ход» (L, 0,4 м): значение для логики |
| `LS103` | `mode` | enum |  |  |  | `LS103.Mode` | Поплавок «сухой ход» (L, 0,4 м): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `LS103` | `ne107` | enum |  |  |  | `LS103.Ne107` | Поплавок «сухой ход» (L, 0,4 м): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `IT111` | `current` | analog | A | 0.2 | 0…60 | `IT111.Value` | Насос Н1: ток двигателя (измеряет ПЧ): итоговое значение |
| `IT111` | `mode` | enum |  |  |  | `IT111.Mode` | Насос Н1: ток двигателя (измеряет ПЧ): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `IT111` | `ne107` | enum |  |  |  | `IT111.Ne107` | Насос Н1: ток двигателя (измеряет ПЧ): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `TS112` | `overheat` | discrete |  |  |  | `TS112.Value` | Насос Н1: перегрев обмотки (термовыключатели, реле защиты насоса): значение для логики |
| `TS112` | `mode` | enum |  |  |  | `TS112.Mode` | Насос Н1: перегрев обмотки (термовыключатели, реле защиты насоса): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `TS112` | `ne107` | enum |  |  |  | `TS112.Ne107` | Насос Н1: перегрев обмотки (термовыключатели, реле защиты насоса): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `MS113` | `leak` | discrete |  |  |  | `MS113.Value` | Насос Н1: протечка в камеру статора (датчик влажности, реле защиты насоса): значение для логики |
| `MS113` | `mode` | enum |  |  |  | `MS113.Mode` | Насос Н1: протечка в камеру статора (датчик влажности, реле защиты насоса): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `MS113` | `ne107` | enum |  |  |  | `MS113.Ne107` | Насос Н1: протечка в камеру статора (датчик влажности, реле защиты насоса): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `IT121` | `current` | analog | A | 0.2 | 0…60 | `IT121.Value` | Насос Н2: ток двигателя (измеряет ПЧ): итоговое значение |
| `IT121` | `mode` | enum |  |  |  | `IT121.Mode` | Насос Н2: ток двигателя (измеряет ПЧ): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `IT121` | `ne107` | enum |  |  |  | `IT121.Ne107` | Насос Н2: ток двигателя (измеряет ПЧ): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `TS122` | `overheat` | discrete |  |  |  | `TS122.Value` | Насос Н2: перегрев обмотки (термовыключатели, реле защиты насоса): значение для логики |
| `TS122` | `mode` | enum |  |  |  | `TS122.Mode` | Насос Н2: перегрев обмотки (термовыключатели, реле защиты насоса): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `TS122` | `ne107` | enum |  |  |  | `TS122.Ne107` | Насос Н2: перегрев обмотки (термовыключатели, реле защиты насоса): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `MS123` | `leak` | discrete |  |  |  | `MS123.Value` | Насос Н2: протечка в камеру статора (датчик влажности, реле защиты насоса): значение для логики |
| `MS123` | `mode` | enum |  |  |  | `MS123.Mode` | Насос Н2: протечка в камеру статора (датчик влажности, реле защиты насоса): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `MS123` | `ne107` | enum |  |  |  | `MS123.Ne107` | Насос Н2: протечка в камеру статора (датчик влажности, реле защиты насоса): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `IT131` | `current` | analog | A | 0.2 | 0…60 | `IT131.Value` | Насос Н3: ток двигателя (измеряет ПЧ): итоговое значение |
| `IT131` | `mode` | enum |  |  |  | `IT131.Mode` | Насос Н3: ток двигателя (измеряет ПЧ): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `IT131` | `ne107` | enum |  |  |  | `IT131.Ne107` | Насос Н3: ток двигателя (измеряет ПЧ): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `TS132` | `overheat` | discrete |  |  |  | `TS132.Value` | Насос Н3: перегрев обмотки (термовыключатели, реле защиты насоса): значение для логики |
| `TS132` | `mode` | enum |  |  |  | `TS132.Mode` | Насос Н3: перегрев обмотки (термовыключатели, реле защиты насоса): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `TS132` | `ne107` | enum |  |  |  | `TS132.Ne107` | Насос Н3: перегрев обмотки (термовыключатели, реле защиты насоса): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `MS133` | `leak` | discrete |  |  |  | `MS133.Value` | Насос Н3: протечка в камеру статора (датчик влажности, реле защиты насоса): значение для логики |
| `MS133` | `mode` | enum |  |  |  | `MS133.Mode` | Насос Н3: протечка в камеру статора (датчик влажности, реле защиты насоса): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `MS133` | `ne107` | enum |  |  |  | `MS133.Ne107` | Насос Н3: протечка в камеру статора (датчик влажности, реле защиты насоса): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `PT201` | `pressure` | analog | bar | 0.02 | 0…10 | `PT201.Value` | Давление в напорном коллекторе: итоговое значение |
| `PT201` | `mode` | enum |  |  |  | `PT201.Mode` | Давление в напорном коллекторе: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `PT201` | `ne107` | enum |  |  |  | `PT201.Ne107` | Давление в напорном коллекторе: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `FT202` | `flow` | analog | m3/h | 2 | 0…500 | `FT202.Value` | Расход в напорном коллекторе: итоговое значение |
| `FT202` | `mode` | enum |  |  |  | `FT202.Mode` | Расход в напорном коллекторе: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `FT202` | `ne107` | enum |  |  |  | `FT202.Ne107` | Расход в напорном коллекторе: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `LS203` | `flood` | discrete |  |  |  | `LS203.Value` | Затопление камеры задвижек: значение для логики |
| `LS203` | `mode` | enum |  |  |  | `LS203.Mode` | Затопление камеры задвижек: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `LS203` | `ne107` | enum |  |  |  | `LS203.Ne107` | Затопление камеры задвижек: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `ES301` | `power_ok` | discrete |  |  |  | `ES301.Value` | Напряжение на вводе в норме (реле контроля фаз): значение для логики |
| `ES301` | `mode` | enum |  |  |  | `ES301.Mode` | Напряжение на вводе в норме (реле контроля фаз): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `ES301` | `ne107` | enum |  |  |  | `ES301.Ne107` | Напряжение на вводе в норме (реле контроля фаз): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `YS302` | `on_battery` | discrete |  |  |  | `YS302.Value` | ИБП шкафа управления: работа от батарей: значение для логики |
| `YS302` | `mode` | enum |  |  |  | `YS302.Mode` | ИБП шкафа управления: работа от батарей: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `YS302` | `ne107` | enum |  |  |  | `YS302.Ne107` | ИБП шкафа управления: работа от батарей: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `YS303` | `ups_fault` | discrete |  |  |  | `YS303.Value` | ИБП шкафа управления: неисправность или разряд батарей: значение для логики |
| `YS303` | `mode` | enum |  |  |  | `YS303.Mode` | ИБП шкафа управления: неисправность или разряд батарей: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `YS303` | `ne107` | enum |  |  |  | `YS303.Ne107` | ИБП шкафа управления: неисправность или разряд батарей: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `AT401` | `h2s` | analog | mg/m3 | 0.2 | 0…40 | `AT401.Value` | Концентрация сероводорода H₂S в павильоне: итоговое значение |
| `AT401` | `mode` | enum |  |  |  | `AT401.Mode` | Концентрация сероводорода H₂S в павильоне: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `AT401` | `ne107` | enum |  |  |  | `AT401.Ne107` | Концентрация сероводорода H₂S в павильоне: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `AT402` | `ch4` | analog | %LEL | 0.5 | 0…100 | `AT402.Value` | Концентрация метана CH₄ в павильоне: итоговое значение |
| `AT402` | `mode` | enum |  |  |  | `AT402.Mode` | Концентрация метана CH₄ в павильоне: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `AT402` | `ne107` | enum |  |  |  | `AT402.Ne107` | Концентрация метана CH₄ в павильоне: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `TT403` | `temperature` | analog | degC | 0.2 | -40…60 | `TT403.Value` | Температура воздуха в павильоне: итоговое значение |
| `TT403` | `mode` | enum |  |  |  | `TT403.Mode` | Температура воздуха в павильоне: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `TT403` | `ne107` | enum |  |  |  | `TT403.Ne107` | Температура воздуха в павильоне: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `ZS404` | `door_open` | discrete |  |  |  | `ZS404.Value` | Дверь павильона открыта: значение для логики |
| `ZS404` | `mode` | enum |  |  |  | `ZS404.Mode` | Дверь павильона открыта: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `ZS404` | `ne107` | enum |  |  |  | `ZS404.Ne107` | Дверь павильона открыта: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `YS405` | `fire` | discrete |  |  |  | `YS405.Value` | Пожар (сигнал прибора пожарной сигнализации): значение для логики |
| `YS405` | `mode` | enum |  |  |  | `YS405.Mode` | Пожар (сигнал прибора пожарной сигнализации): режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `YS405` | `ne107` | enum |  |  |  | `YS405.Ne107` | Пожар (сигнал прибора пожарной сигнализации): статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `K1` | `general_alarm` | discrete |  |  |  | `K1` | Общая авария: реле K1 «Общая авария» обесточено (в норме реле под напряжением, сухой контакт в диспетчерскую) |
| `KNS1` | `mode` | enum |  |  |  | `KNS1.Mode` | Станция КНС-1: режим: 1 Auto, 2 Manual |
| `KNS1` | `method` | enum |  |  |  | `KNS1.Method` | Станция КНС-1: способ регулирования: 1 ступенчатое, 2 ПИД уровня |
| `KNS1` | `control` | enum |  |  |  | `KNS1.ControlAct` | Станция КНС-1: действующее управление: 0 ручное, 1 ступенчатое, 2 ПИД уровня, 3 по поплавкам, 4 аварийный уровень, 5 сухой ход, 6 нет напряжения, 7 перезапуск |
| `KNS1` | `ne107` | enum |  |  |  | `KNS1.Ne107` | Станция КНС-1: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `KNS1` | `state` | integer |  |  |  | `KNS1.State` | Станция КНС-1: слово состояния (биты STN_ST_* флагмана) |
| `KNS1` | `pumps_required` | integer |  |  |  | `KNS1.PumpsRequired` | Станция КНС-1: требуется насосов |
| `KNS1` | `pumps_running` | integer |  |  |  | `KNS1.PumpsRunning` | Станция КНС-1: насосов в работе |
| `KNS1` | `pumps_available` | integer |  |  |  | `KNS1.PumpsAvailable` | Станция КНС-1: насосов доступно в автомате |
| `KNS1` | `lead` | integer |  |  |  | `KNS1.LeadPump` | Станция КНС-1: ведущий насос: 1–3, 0 — нет |
| `KNS1` | `seq_remain` | integer | s |  |  | `KNS1.SeqRemain` | Станция КНС-1: до следующего шага последовательного пуска |
| `KNS1` | `level` | analog | m | 0.01 |  | `KNS1.Level` | Станция КНС-1: уровень, по которому работает станция |
| `KNS1` | `level_sp` | analog | m | 0.01 |  | `KNS1.LevelSp` | Станция КНС-1: действующее задание уровня |
| `KNS1` | `speed_sp` | analog | % | 0.5 |  | `KNS1.SpeedSp` | Станция КНС-1: общее задание частоты насосам |
| `LIC101` | `pv` | analog | m | 0.01 |  | `LIC101.Pv` | Регулятор уровня LIC101: регулируемая величина (уровень) |
| `LIC101` | `sp` | analog | m | 0.01 |  | `LIC101.Sp` | Регулятор уровня LIC101: действующее задание |
| `LIC101` | `out` | analog | % | 0.5 |  | `LIC101.Out` | Регулятор уровня LIC101: выход (задание частоты) |
| `LIC101` | `mode` | enum |  |  |  | `LIC101.Mode` | Регулятор уровня LIC101: режим: 1 Auto, 2 Manual, 3 Local, 4 OutOfService |
| `LIC101` | `ne107` | enum |  |  |  | `LIC101.Ne107` | Регулятор уровня LIC101: статус NE 107: 0 Good, 1 M, 2 S, 3 C, 4 F |
| `PLC1` | `uptime` | counter | s |  |  | — | Шлюз MQTT ПЛК: время работы ПЛК с последнего запуска приложения |
| `PLC1` | `reconnects` | counter |  |  |  | — | Шлюз MQTT ПЛК: переподключений к брокеру MQTT с запуска |
| `PLC1` | `queue` | integer |  |  |  | — | Шлюз MQTT ПЛК: сообщений в очереди на отправку |
| `PLC1` | `dropped` | counter |  |  |  | — | Шлюз MQTT ПЛК: сообщений, отброшенных при переполнении очереди |
| `PLC1` | `cmd_accepted` | counter |  |  |  | — | Шлюз MQTT ПЛК: принятых команд MQTT с запуска |
| `PLC1` | `cmd_rejected` | counter |  |  |  | — | Шлюз MQTT ПЛК: отклонённых команд MQTT с запуска |
<!-- END GENERATED: telemetry-catalog -->

Таблица выше генерируется из `schema/telemetry_catalog.csv` (`python tools_project/gen_config.py`).

## 4. Тревоги

### 4.1 Сообщение

Топик `vodokanal/kns1/station/LT101/alarm/HH`:

```json
{"schema_version": "1.1", "ts": 1792137605000, "id": 1010, "code": "LT101.HH", "priority": "High",
 "state": "ActiveUnack", "prev_state": "Normal", "reason": "Activated", "value": 4.03}
```

| Поле | Смысл |
|---|---|
| `id` | `udiId` тревоги: у устройств `dev_no · 10 + слот` (перечень iolistgen), у станции `100000 + slot` (`KNS1.EHL` — 100001 … `KNS1.SIM` — 100013) |
| `code` | `<DEVICE>.<SUFFIX>`; DEVICE и SUFFIX совпадают с уровнями топика; суффикс — `[A-Z][A-Z0-9]{0,7}` (`HH`, `FTS`, `NOAUTO`, `UL1`) |
| `priority` | `Low`, `Medium`, `High`, `Critical` (E_AlarmPriority) |
| `state`, `prev_state` | состояние после и до события (E_AlarmState): `Normal`, `ActiveUnack`, `ActiveAck`, `RtnUnack`, `Shelved`, `SuppressedByDesign`, `OutOfService` |
| `reason` | причина (E_AlarmEventReason): `Activated`, `Cleared`, `Acked`, `Shelved`, `Unshelved`, `ShelveExpired`, `Suppressed`, `Unsuppressed`, `OosOn`, `OosOff` |
| `value` | значение процесса в момент события, если есть |

- Одно сообщение — одно событие `ST_AlarmEvent` библиотеки. С `retain` последнее событие тревоги
  служит её текущим состоянием: «активные сейчас» = последний `state` по каждому `code`.
- После рождения узла (раздел 6) публикуются все тревоги. Тревога, чьё состояние не менялось,
  повторяется последним опубликованным сообщением **с исходным `ts`**: в InfluxDB это та же точка, и
  переподключение ПЛК не добавляет срабатываний (`reason = Activated`) на дашбордах и в отчёте.
  Переход, случившийся без связи, — событие с текущим `ts`; тревога, ещё не публиковавшаяся с запуска
  узла, — снимок с `prev_state = state`.
- Русского текста в сообщении нет: строки в ПЛК 3.5.17 — Windows-1252 (API plc-process-lib,
  раздел 19). Текст по коду добавляет Telegraf (тег `text`) из `telegraf/lookup/alarm_texts.json`,
  который генерируется из `schema/source/scada_alarms.csv` и `station_alarms.csv`.
- Тревоги станции (`KNS1.*`, 13 тревог, источник — `docs/05_alarm_list.csv` флагмана) публикуются так
  же, по словам `GVL_Station.stStationSts.wAlmActive`, `wAlmUnack`, `wAlmShelved` (бит = slot − 1).
  Тревога регулятора `LIC101.PVF` во флагмане выключена (приоритет None) и в перечень не входит.

## 5. Команды

### 5.1 Сообщение и проверки

Топик `vodokanal/kns1/station/P101/cmd/SpeedSp`:

```json
{"schema_version": "1.1", "cmd_id": "b0e7c3d1-5a2f-4e8b-8c61-9d4a7f2e1b33", "ts": 1792137621000,
 "origin": "operator1@grafana", "command": "SpeedSp", "value": 75.0}
```

`command` — имя поля `ST_<Dev>Cmd` без префикса типа (`xStart` → `Start`, `rSpeedSp_pct` →
`SpeedSp`, `stCommon.xAck` → `Ack`). `value` есть только у команд-значений (`SpeedSp`, `SubstValue`)
и масок (`AckReq`, `ShelveReq`, `UnshelveReq`); у импульсных команд его быть не должно. Схема
команды строгая (`additionalProperties: false`): лишнее поле — ошибка.

ПЛК проверяет команду по порядку и на первую же ошибку отвечает `rejected` с причиной:

| № | Проверка | `reason` |
|---|---|---|
| 1 | сообщение пришло с флагом retain | `retained` |
| 2 | JSON разобран; состав полей и типы — по `command.schema.json` (диапазон `value` — проверка 6) | `invalid_payload` |
| 3 | мажорная версия `schema_version` = 1 | `unsupported_version` |
| 4 | `command` совпадает с последним уровнем топика | `topic_mismatch` |
| 5 | пара (устройство, команда) есть в белом списке | `not_whitelisted` |
| 6 | `value` в диапазоне `[min; max]` белого списка | `out_of_range` |
| 7 | `ts` не старше допуска (30 с; часы ПЛК синхронизированы по NTP) | `expired` |
| 8 | `cmd_id` не встречался среди последних 16 команд | `duplicate` |
| 9 | не больше 10 команд за 10 с | `rate_limited` |
| 10 | команда записана в `GVL_Hmi.st<DEV>Cmd`, устройство её обработало (`uiCmdSeq` +1, `eCmdResult`) | `ok` / `device_rejected` / `timeout` |

Схема команды задаёт и диапазон `SpeedSp` (0…100 %), но шлюз проверяет значение отдельно, шагом 6:
так отправитель получает `out_of_range`, а не общее `invalid_payload`. Так делают и ПЛК
(`FB_MqttCommands.Check`), и эмулятор (`commands.py`); полная проверка по схеме (`jsonschema`) — у
отправителя и в тестах.

Если `cmd_id` прочитать нельзя (не JSON), ответа нет: ПЛК увеличивает счётчик `PLC1/cmd_rejected`.
Для команд-значений (`SpeedSp`) устройство не увеличивает `uiCmdSeq` — ответ `ok` даётся после
записи (сверить с реализацией `FB_MotorVfd`).

### 5.2 Белый список

По MQTT разрешён минимальный набор: режим Авто/Ручной, пуск, стоп и задание скорости насосов,
квитирование и сброс устройств; у станции `KNS1` — режим, способ регулирования, общее квитирование,
общий сброс и «Отключить звук», у регулятора `LIC101` — режим Авто/Ручной. Выгрузка журнала, откат
уставок станции и номера тревог (`ExportLog`, `RevertCfg`, `udiAckId`…) — только с местной HMI и по
OPC UA. Не разрешены и отклоняются как `not_whitelisted`: `SetOos` (вывод из работы),
`ResetMaint` (сброс счётчиков ТО), `SubstValue` (подмена значения), `ShelveReq`/`UnshelveReq`/`AckReq`
(маски тревог) — это действия обслуживающего персонала с местной HMI.

<!-- BEGIN GENERATED: command-whitelist -->
| Устройства | Разрешённые команды |
|---|---|
| `P101`, `P102`, `P103` | `SetAuto`, `SetManual`, `Start`, `Stop`, `SpeedSp` (0…100 %), `Ack`, `Reset` |
| `V1` | `SetAuto`, `SetManual`, `Start`, `Stop`, `Ack`, `Reset` |
| `LT101`, `LS102`, `LS103`, `IT111`, `TS112`, `MS113`, `IT121`, `TS122`, `MS123`, `IT131`, `TS132`, `MS133`, `PT201`, `FT202`, `LS203`, `ES301`, `YS302`, `YS303`, `AT401`, `AT402`, `TT403`, `ZS404`, `YS405`, `HS501`, `HS502` | `Ack`, `Reset` |
| `KNS1` | `SetAuto`, `SetManual`, `SetStepped`, `SetLevelPid`, `AckAll`, `ResetAll`, `Silence` |
| `LIC101` | `SetAuto`, `SetManual` |
<!-- END GENERATED: command-whitelist -->

Полный список с путями в ПЛК — `schema/command_whitelist.csv`.

### 5.3 Ответ

Топик `vodokanal/kns1/station/P101/cmd_ack/SetOos`:

```json
{"schema_version": "1.1", "cmd_id": "c4d9e1f2-7b3a-4d6c-9e85-1a2b3c4d5e6f", "ts": 1792137622010,
 "command": "SetOos", "result": "rejected", "reason": "not_whitelisted"}
```

`result = accepted` только с `reason = ok`. При `reason = device_rejected` обязателен `cmd_result` —
значение E_CmdResult устройства (`RejectedMode`, `RejectedInterlock`, `RejectedPermit`,
`RejectedInhibit`, `RejectedFault`, `RejectedState`, `RejectedNotSupported`, `RejectedCfg`).

## 6. Состояние узла

Топик `vodokanal/kns1/station/PLC1/status/connection`, retain:

| Момент | Сообщение |
|---|---|
| подключение к брокеру | завещание (LWT) того же топика: `{"state": "offline", "reason": "lwt", "ts": <время подключения>}` |
| сразу после подключения | рождение: `{"state": "online", "reason": "birth", "source": "codesys", "sw_version": "…", "period_ms": 60000}`, затем контрольная публикация всех метрик и всех тревог (раздел 4.1: неизменившиеся — повтором с исходным `ts`) |
| штатная остановка | `{"state": "offline", "reason": "shutdown"}` |

`ts` завещания — время подключения: текст LWT передаётся брокеру заранее.

## 7. Хранение в InfluxDB

### 7.1 Модель

Telegraf пишет в бакет сырых данных (`INFLUX_BUCKET`, по умолчанию `kns_raw`, хранение 30 сут).
Задача `kns_downsample_1h` раз в час пишет агрегаты в бакет `INFLUX_BUCKET_AGG` (`kns_agg`, 730 сут).

<!-- BEGIN: influx-model -->
| Measurement | Бакет | Откуда | Теги | Поля |
|---|---|---|---|---|
| `telemetry` | `kns_raw` | MQTT телеметрия; OPC UA (опрос Telegraf) | `site`, `area`, `unit`, `device`, `metric`, `source` | `value` (float), `quality` (string), `opcua_status` (string) |
| `alarm` | `kns_raw` | MQTT `…/alarm/{suffix}` | `site`, `area`, `unit`, `device`, `suffix`, `code`, `priority`, `text` | `id` (integer), `state` (string), `prev_state` (string), `reason` (string), `value` (float) |
| `command` | `kns_raw` | MQTT `…/cmd/{command}` | `site`, `area`, `unit`, `device`, `command` | `cmd_id` (string), `origin` (string), `value` (float) |
| `command_ack` | `kns_raw` | MQTT `…/cmd_ack/{command}` | `site`, `area`, `unit`, `device`, `command`, `result` | `cmd_id` (string), `reason` (string), `cmd_result` (string) |
| `node_status` | `kns_raw` | MQTT `…/status/connection` | `site`, `area`, `unit`, `device` | `state` (string), `reason` (string), `source` (string), `sw_version` (string) |
| `telemetry_1h` | `kns_agg` | задача `kns_downsample_1h` | `site`, `area`, `unit`, `device`, `metric`, `source` | `mean` (float), `min` (float), `max` (float) |
<!-- END: influx-model -->

- Тег `source`: `mqtt` — значение опубликовал ПЛК, `opcua` — Telegraf прочитал его с OPC UA-сервера.
  Оба пути пишут одинаковые `device`/`metric`; дашборды выбирают путь переменной «Источник».
- `quality` — только у `source = mqtt`, `opcua_status` (код статуса OPC UA текстом Telegraf 1.39,
  например `The operation succeeded. StatusGood (0x0)`) — только у `source = opcua`.
- Время точки MQTT — `ts` из сообщения (время ПЛК), точки OPC UA — время опроса Telegraf.
  Исключение — `node_status`: время приёма Telegraf. У завещания `ts` — время подключения (раздел 6),
  и с ним точка `offline` легла бы раньше рождения того же подключения: «последнее состояние узла»
  в базе навсегда осталось бы `online`. Сохранённое (retain) сообщение, повторно полученное после
  перезапуска Telegraf, даёт новую точку с тем же состоянием — это и есть текущее состояние узла.
- `cmd_id` — поле, а не тег: уникальные значения в тегах раздувают индекс серий.
- `schema_version` в базу не пишется: Telegraf принимает только версии `1.x` (фильтр `tagpass`).
- `telemetry_1h`: точка агрегата стоит на **конце** часа (`_time` = 10:00 для часа 09:00–10:00).
  `mean` — среднее, **взвешенное по времени**: значение действует от своей точки до следующей, но не
  дольше 10 мин, значение до начала часа действует и в нём. Простое среднее по точкам для MQTT
  смещено: при публикации по изменению точек больше там, где значение быстро менялось (на данных
  стенда — уровень 1,27 м против 1,21 м взвешенного). `min`, `max` — по значениям, действовавшим в
  течение часа. Точки с `quality = bad` в агрегаты не входят — методика та же, что у суточного
  отчёта (`report/README.md`).
- Время точек телеметрии, тревог и команд — часы ПЛК (`ts`); Telegraf его не проверяет. Часы ПЛК
  синхронизируются по NTP: точки «из будущего» не видны на дашбордах с концом диапазона «сейчас»,
  отставание часов сдвигает историю (панель обзора «Обновлено» — возраст данных — показывает
  расхождение).

### 7.2 Пример запроса

```flux
from(bucket: "kns_raw")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "telemetry" and r._field == "value" and r.source == "mqtt")
  |> filter(fn: (r) => r.device == "LT101" and r.metric == "level")
  |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
```

## 8. Версионирование

`schema_version` = `MAJOR.MINOR`, обязательно в каждом сообщении. Версия общая для всех классов.

| Изменение | Версия | Пример |
|---|---|---|
| новое необязательное поле, новая метрика в каталоге, новое значение причины отказа | MINOR (1.0 → 1.1) | поле `seq` в телеметрии |
| удаление или переименование поля, смена типа или единиц, смена смысла, новый уровень топика, новое обязательное поле | MAJOR (1.x → 2.0) | `ts` в секундах вместо мс |

Правила:
1. Получатель принимает любую MINOR своей MAJOR и игнорирует неизвестные поля (кроме команд:
   схема команды строгая, лишнее поле — отказ). Сообщения другой MAJOR не обрабатываются: Telegraf
   их отбрасывает, ПЛК отвечает `unsupported_version`.
2. Переход на новую MAJOR — с периодом совместимости: публикатор шлёт обе версии в разные
   корни топиков (`vodokanal/…` и `vodokanal_v2/…`), пока все получатели не перейдут.
3. Переименование метрики — MAJOR: история в InfluxDB привязана к тегу `metric`.
4. Изменения схемы фиксируются в `CHANGELOG.md` и в `$id` файлов (`urn:plc-iiot-stack:schema:<класс>:<MAJOR>`).

| Версия | Что изменилось |
|---|---|
| 1.0 | первая версия: устройства перечня сигналов флагмана, узел PLC1 |
| 1.1 | привязка к флагману kns-pump-station: метрики станции `KNS1/*` и регулятора `LIC101/*`, команды `SetStepped`, `SetLevelPid`, `AckAll`, `ResetAll`, `Silence`, тревоги станции `KNS1.*` (номер до 4294967295, суффикс `[A-Z][A-Z0-9]{0,7}` вместо `[A-Z]{1,4}`), колонка `invert` каталога; смысл `K1/general_alarm` (1 — общая авария) не менялся — во флагмане реле K1 в норме под напряжением, и метрика теперь это учитывает. Сообщения 1.0 остаются действительными |

## 9. Проверки

| Что | Где |
|---|---|
| схемы — валидный JSON Schema 2020-12, примеры им соответствуют, топики примеров разбираются | `tests_stack/test_schema.py` |
| каталог и белый список сходятся с перечнем iolistgen | `tests_stack/test_catalog.py` |
| пути каталога, белого списка, тегов эмулятора, узлов Telegraf и сгенерированного ST — настоящие символы флагмана с тем же типом; писать можно только в структуры команд (обе сборки флагмана) | `tests_stack/test_flagship_binding.py` |
| Telegraf пишет только объявленные measurement, теги и поля; подписки совпадают с `topics.json` | `tests_stack/test_telegraf.py` |
| запросы дашбордов ссылаются на объявленные measurement, поля, теги и метрики каталога | `tests_stack/test_grafana.py` |
| образы закреплены по версии, секретов в отслеживаемых файлах нет | `tests_stack/test_compose.py` |
| сгенерированные файлы актуальны, `make env`, ожидание готовности, `Makefile` и `make.ps1` согласованы | `tests_stack/test_tools.py` |
| сквозной путь «эмулятор → брокер → Telegraf → InfluxDB → запрос» на поднятом стенде: все метрики каталога по MQTT и все узлы OPC UA каталога, ACL, версия схемы, команда вне белого списка и вне диапазона, команда станции, агрегаты задачи прореживания против расчёта по сырым точкам | `tests_stack/test_stack_integration.py` (`make test-stack`) |
| каждая панель трёх дашбордов возвращает данные (запросы выполняет Grafana) | `tools_project/check_dashboards.py` (`make test-stack`) |
| локальный стенд без Docker повторяет конфигурацию compose (пользователи и ACL брокера, переменные, тома) | `tests_stack/test_local_stack.py` |
