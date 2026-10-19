# ПЛК-часть стека: MQTT в CODESYS

ST-код публикует телеметрию, события тревог и состояние узла КНС-1 в брокер MQTT и принимает
команды по контракту [data_schema.md](data_schema.md). Он из двух частей:

- **ядро шлюза** в `src/` — ФБ MQTT, JSON, таблицы схемы; от флагмана не зависит, собирается и
  тестируется в этом репозитории (`cds.py build`, `cds.py test`);
- **привязка к флагману** в `flagship/src/` — программа `PRG_Iiot` и сгенерированный `FB_IiotKnsMap`
  с путями к настоящим переменным kns-pump-station (`GVL_Devices`, `GVL_Hmi`, `GVL_IO`, `GVL_Station`,
  типы `PL.*` plc-process-lib). Собирается только во флагмане (раздел «Привязка к флагману»).

Тексты сообщений, топики, коды и порядок проверок команд совпадают с эмулятором
(`emulator/iiot_emulator/`) и JSON Schema в `schema/`; совпадение имён и кодов проверяет
`tests_stack/test_plc_contract.py`, пути привязки — `tests_stack/test_flagship_binding.py` по снимку
интерфейса флагмана, поведение ядра — тесты coUnit ([TEST_REPORT.md](TEST_REPORT.md): последний прогон
в CODESYS Control Win V3 — 16.10.2026, до привязки к флагману).

Транспорт MQTT спрятан за интерфейсом `I_MqttClient`. Логика не зависит от библиотеки и проверена с
подменным клиентом; адаптер на библиотеку CODESYS-MQTT написан, но не собран с ней: на CODESYS
3.5.17.30 нет её зависимостей ([MANUAL_STEPS.md](MANUAL_STEPS.md#9-библиотека-codesys-mqtt), раздел
«Адаптер I_MqttClient» ниже). Без адаптера `PRG_Iiot` работает с клиентом без транспорта: обмен не
начинается, состояние — «нет связи».

## Состав

| Объект | Что делает |
|---|---|
| `PRG_Iiot` (`flagship/src/`) | обвязка во флагмане: время, клиент, ФБ ниже, теги флагмана; задача `MainTask` после `PRG_Devices` |
| `PRG_Main` | служебная программа рабочей сборки этого репозитория: признак «часы ПЛК установлены» для проверки онлайн |
| `FB_MqttDiag` | связь с брокером: подключение, повторы с паузой, завещание (LWT), рождение и штатное отключение, счётчики, сводный статус NE 107 |
| `FB_MqttTelemetry` | телеметрия: по изменению с зоной нечувствительности и периодически |
| `FB_MqttAlarms` | события тревог по словам тревог устройств и снимок после рождения |
| `FB_MqttCommands` | шлюз команд: подписка, разбор JSON, проверки по порядку контракта, ответ `cmd_ack`, ожидание обработки устройством |
| `FB_JsonBuilder`, `FB_JsonFlatParser` | сборка и разбор плоского JSON без ограничения 255 символов стандартных строковых функций |
| `F_Iiot*` | тексты кодов схемы, качество по NE 107, зона нечувствительности, проверки форматов, топики, время |
| `I_MqttClient`, `FB_MqttClientNone` | интерфейс транспорта и клиент без транспорта (нулевой объект) |
| `GVL_IiotMap` | таблицы метрик, команд и тревог — генерируются из `schema/` |
| `FB_IiotKnsMap` (`flagship/src/`) | привязка к переменным флагмана: значения, качество, слова тревог, запись команд — генерируется из `schema/` |
| `GVL_Iiot` | настройки `stIiotCfg` и состояние `stIiotSts` для HMI и SCADA |
| `adapters/sd_mqtt_1_0/` | адаптер `FB_MqttClientSdMqtt` на CODESYS-MQTT 1.0.0.0 — вне `src/`, не компилировался с библиотекой |

Время работы ФБ — монотонное `LTIME()` (через `F_IiotNow`), а не счёт циклов; поле `ts` — календарное
время ПЛК в мс UTC (`SysTimeRtcHighResGet`, библиотека SysTimeRtc).

## Топики

Префикс `<site>/<area>/<unit>` собирается из `GVL_Iiot.stIiotCfg` (`vodokanal/kns1/station`), хвост —
из таблиц схемы ([data_schema.md, раздел 2](data_schema.md#2-топики)):

| Класс | Топик | QoS | retain | Кто публикует |
|---|---|---|---|---|
| телеметрия | `<prefix>/<DEVICE>/<metric>` | 1 | да | `FB_MqttTelemetry` |
| тревога | `<prefix>/<DEVICE>/alarm/<SUFFIX>` | 1 | да | `FB_MqttAlarms` |
| команда | подписка `<prefix>/+/cmd/+` | 1 | — | `FB_MqttCommands` |
| ответ на команду | `<prefix>/<DEVICE>/cmd_ack/<Command>` | 1 | нет | `FB_MqttCommands` |
| состояние узла | `<prefix>/<sNode>/status/connection` | 1 | да | `FB_MqttDiag` |

`F_IiotTopic` склеивает префикс и хвост и возвращает пустую строку, если топик длиннее
`MQTT_TOPIC_LEN` (127 байт): такое сообщение не публикуется и считается отброшенным, а не обрезается.
Уровни входящего топика команды проверяются по шаблонам схемы (`F_IiotIsName`): устройство —
`[A-Z][A-Z0-9_]{0,15}`, команда — `[A-Za-z][A-Za-z0-9_]{0,31}`.

## Построение JSON

`FB_JsonBuilder` пишет плоский объект побайтно в буфер `STRING(MQTT_PAYLOAD_LEN)` (1023 байта):
стандартные `CONCAT`, `LEN` и т. п. в CODESYS ограничены 255 символами, а сообщение рождения и ответ на
команду длиннее. Порядок: `Begin()`, `AddString/AddInt/AddReal/AddBool/AddNull` по полю, `Finish()`.

- Ключи и строки экранируются по JSON (`"`, `\`, управляющие символы — `\n`, `\t`, `\u00XX`).
- `AddReal` — число знаков из каталога (`uiDecimals`, по умолчанию 3, не больше 6) с округлением и без
  хвостовых нулей: `2.31`, `75`, `-0.5`. NaN и бесконечность — `null`. Если `|x|·10^знаков ≥ 9·10^15`, точности
  LREAL не хватает для честных знаков — тоже `null` (значения процесса КНС до этого не доходят).
- `AddInt` — LINT целиком, включая границы диапазона (проверено тестом `IntExtremes`).
- Не поместилось — флаг `xOverflow`, `Finish()` возвращает FALSE: неполный JSON не публикуется, вызывающий
  ФБ считает сообщение отброшенным (`udiDropped`). Повторять бессмысленно: размер не изменится.

Разбор команд — `FB_JsonFlatParser`, раздел «Команды».

## Телеметрия

`FB_MqttTelemetry` обходит таблицу `aPoints` (одна строка — одна метрика каталога) и публикует
сообщение [data_schema.md, 3.1](data_schema.md#31-сообщение):

```json
{"schema_version":"1.0","ts":1792137600250,"value":2.31,"quality":"good","unit":"m"}
```

Когда метрика публикуется (`PointDue`):

1. ещё не публиковалась после рождения узла, запрошена контрольная публикация (`ForceAll`) или
   изменилось `quality` — сразу;
2. иначе не чаще `tMinInterval` (1 с) на метрику;
3. аналоговая — если значение ушло от опубликованного **больше** зоны нечувствительности `deadband`
   каталога (`F_IiotDeadbandExceeded`, строгое `>`); целые, дискретные и перечисления — при любом
   изменении. Зона ≤ 0 или не число — любое изменение; переход между числом и NaN/бесконечностью —
   изменение, между двумя неконечными — нет;
4. контрольная публикация всех метрик — раз в `tPeriod` (`stIiotCfg.tTelemetryPeriod`, 60 с; `T#0S` —
   без неё) и после каждого рождения (`xReady` с FALSE на TRUE). Метрики с `xPeriodicOnly`
   публикуются только так.

За вызов — не больше `uiMaxPerCycle` (8) публикаций, обход по кругу с места остановки: ни одна метрика
не ждёт вечно, очередь клиента не переполняется. Клиент не принял сообщение (нет места) — `udiFailed`,
метрика повторится; сообщение не собралось — `udiDropped`. `uiPending` — сколько метрик ждут.

Качество (`F_IiotQuality`, [data_schema.md, 3.2](data_schema.md#32-достоверность)): `eNe107` = Failure —
`bad`; CheckFunction или OutOfSpecification — `uncertain`; Good или MaintenanceRequired при `xValid` —
`good`, без `xValid` — `bad`. У метрик ПЧ (`speed`, `vfd_fault_code`) потеря связи даёт `bad`: бит
`PL.GVL_Const.MOT_FLT_COMM_LOSS` в `wFault` или, если потеря связи настроена предупреждением
(`xCommLossIsFault = FALSE`), бит `PL.GVL_Const.MOT_WRN_COMM_LOSS` в `wWarning` — константы самой
библиотеки, своих копий кодов у привязки нет. Значение не конечно (NaN, ±Inf; устройства библиотеки так не отдают, но
метрику может заполнить и приложение): `value` по схеме — всегда число, поэтому передаётся последнее
опубликованное конечное значение (`lrLastFinite`) с `quality = bad` — как требует
[data_schema.md, 3.2](data_schema.md#32-достоверность); `null` в телеметрию не попадает (тест
`NotFiniteValueSendsLastFiniteAsBad`).

## Тревоги

`FB_MqttAlarms` ведёт состояние каждой тревоги перечня по словам тревог источника и публикует событие
[data_schema.md, 4.1](data_schema.md#41-сообщение) при смене состояния с прошлой публикации:

```json
{"schema_version":"1.0","ts":1792137605000,"id":1010,"code":"LT101.HH","priority":"High",
 "state":"ActiveUnack","prev_state":"Normal","reason":"Activated"}
```

- Слова источника (`ST_IiotAlarmWords`): у устройств — `wAlmActive`, `wAlmUnack`, `wAlmShelved`,
  `wAlmSuppressed` из `stSts.stCommon` (plc-process-lib 1.0) и режим OutOfService; у станции KNS1 —
  `GVL_Station.stStationSts.wAlmActive`, `wAlmUnack`, `wAlmShelved` (бит = slot − 1; в `wAlmShelved`
  станции флагман объединяет отложенные, подавленные и выведенные — они публикуются как `Shelved`).
- Состояние слота (`F_IiotAlarmStateOf`, старшинство plc-process-lib): вывод из работы →
  `OutOfService`, бит в `wSuppressed` → `SuppressedByDesign`, бит в `wShelved` → `Shelved`, активна и не
  квитирована → `ActiveUnack`, активна → `ActiveAck`, не квитирована → `RtnUnack`, иначе `Normal`.
- Номер тревоги — `UDINT` (`ST_IiotAlarmCfg.udiId`): у станции 100001…100013; суффикс — до 8 знаков
  (`IIOT_SUFFIX_LEN`: `NOAUTO`, `UL1`).
- Причина — по переходу (`F_IiotAlarmReason`): в `ActiveUnack` — `Activated`; `ActiveUnack → ActiveAck`
  и `RtnUnack → Normal` — `Acked`; в `RtnUnack` и `ActiveAck → Normal` — `Cleared`; в `Shelved` и
  обратно — `Shelved`/`Unshelved`, в `OutOfService` и обратно — `OosOn`/`OosOff` (проверяет тест
  `AlarmReasonByTransition`).
- После каждого рождения публикуются все тревоги, и с `retain` последний `state` по каждому `code` —
  текущее состояние тревоги для дашборда:
  - состояние не менялось с прошлой публикации — она повторяется как есть, с исходными `ts` и
    `prev_state`. В InfluxDB это та же точка: активная тревога после переподключения ПЛК не
    считается новым срабатыванием (`reason = Activated`) на дашбордах и в отчёте;
  - состояние изменилось, пока связи не было, — событие с текущим `ts` и `prev_state` последней
    публикации;
  - тревога с запуска ПЛК ещё не публиковалась — снимок: `prev_state = state`, текущий `ts`.

  Для повтора `ST_IiotAlarm` хранит `ts` и `prev_state` последней публикации (`uliEventTs_ms`,
  `eEventPrev`); проверяют тесты `ReconnectRepeatsLastEventWithItsTs` и
  `ChangeWhileOfflineIsEventAfterReconnect`.
- `value` (значение процесса в момент события) не передаётся: поле необязательное, а слова тревог
  его не содержат.

Ограничение подхода: переходы между двумя публикациями сливаются в один (например, тревога, которая
появилась и ушла за один цикл ПЛК, не видна). Точные события `ST_AlarmEvent` во флагмане даёт приёмник
`PL.I_AlarmSink` библиотеки plc-process-lib; переход на него — дальнейший шаг при встраивании во флагман.

## Команды

`FB_MqttCommands` подписывается на `<prefix>/+/cmd/+` (QoS 1) после подключения и заново после каждого
переподключения (сессия может быть чистой) и разбирает не больше `uiMaxPerCycle` (1) сообщения за цикл.

**Разбор** — `FB_JsonFlatParser`: один плоский объект; значения — строки до `JSON_STR_LEN` (64) с
escape-последовательностями ASCII, числа по грамматике JSON в диапазоне REAL (с признаком «целое
без дробной части и порядка», `FieldIsInteger`), `true`, `false`, `null`. Вложенные объекты и массивы,
повторяющиеся ключи, управляющие символы в строке, лишние символы после объекта, больше
`JSON_MAX_FIELDS` (12) полей — отказ с причиной `eError` и позицией `uiErrorPos`.

**Проверки** — по порядку [data_schema.md, 5.1](data_schema.md#51-сообщение-и-проверки), на первую
ошибку — ответ `rejected` с причиной (метод `Check`):

| № | Проверка | `reason` |
|---|---|---|
| 1 | сообщение пришло с флагом retain | `retained` |
| 2 | JSON разобран; поля и типы по `command.schema.json`: строгий состав полей, `schema_version` вида `N.M`, `ts` — целое в диапазоне схемы, `origin` — печатный ASCII до 64 символов, `command` — известное имя, `value` есть только у команд-значений и масок (маска — целое 0…65535) | `invalid_payload` |
| 3 | мажорная версия = `IIOT_SCHEMA_MAJOR` (1) | `unsupported_version` |
| 4 | `command` = последний уровень топика | `topic_mismatch` |
| 5 | пара (устройство, команда) в белом списке `GVL_IiotMap.RULE_CFG` | `not_whitelisted` |
| 6 | `value` в `[rMin; rMax]` строки белого списка; для `SpeedSp` дополнительно 0…100 % | `out_of_range` |
| 7 | часы ПЛК установлены и `|время ПЛК − ts| ≤ 30 с` | `expired` |
| 8 | `cmd_id` не встречался среди последних 16 команд (запоминаются все проверенные, кроме самих повторов) | `duplicate` |
| 9 | не больше 10 команд за 10 с (скользящее окно по `LTIME`) | `rate_limited` |
| 10 | команда записана в `GVL_Hmi.st<DEV>Cmd` (станция — `GVL_Station.stStationCmd`, регулятор — `stLIC101Cmd`), устройство её обработало | `ok` / `device_rejected` / `timeout` |

Без ответа (ответить некуда или нечем связать ответ с командой) — счётчик `udiDropped` и метрика
`PLC1/cmd_rejected`:

- топик не своей станции или с уровнями не по шаблону;
- текст длиннее `MQTT_CMD_PAYLOAD_LEN` (511 байт) или не JSON-объект;
- нет `cmd_id` или он не по шаблону `[A-Za-z0-9_-]{8,36}`.

Проверка 2 (`invalid_payload`) выполняется, когда JSON разобран и `cmd_id` прочитан.

**Исполнение.** Прошедшая проверки команда — импульс `xCmdValid` и `stCmd` (строка белого списка,
устройство, команда, значение). `PRG_Iiot` в том же цикле запоминает `uiCmdSeq` устройства
(`FB_IiotKnsMap.DeviceCmdState`), пишет команду в `GVL_Hmi` (`ApplyCommand`: импульс `TRUE` или
значение) и вызывает `Arm(uiSeqBefore)`. Дальше ФБ ждёт, пока устройство увеличит `uiCmdSeq`:
`eCmdResult` = Accepted — `ok`, иначе `device_rejected` с `cmd_result`; нет за `tDeviceTimeout` (3 с) —
`timeout`. Команды-значения (`SpeedSp`) устройство не квитирует счётчиком — `ok` сразу после записи
(сверить с `FB_MotorVfd` флагмана). Пока команда в обработке (`xPending`), новые сообщения не
забираются из очереди клиента: одна команда за раз.

**Ответ** ([data_schema.md, 5.3](data_schema.md#53-ответ)) — QoS 1 без retain:

```json
{"schema_version":"1.0","cmd_id":"b0e7c3d1-5a2f-4e8b-8c61-9d4a7f2e1b33","ts":1792137622010,
 "command":"SpeedSp","result":"accepted","reason":"ok"}
```

Ответ, который клиент не принял, не повторяется (`udiAckFailed`, метрика `PLC1/dropped`): отправитель
команды по схеме ждёт ответ ограниченное время и повторяет команду с новым `cmd_id`.

Приём команд выключен, пока не включены оба флага `stIiotCfg.xEnable` и `stIiotCfg.xCommandsEnable`
(по умолчанию оба FALSE).

## Связь и состояние узла

`FB_MqttDiag` — конечный автомат:

| Состояние | Что происходит | Переход |
|---|---|---|
| `Disabled` | обмен выключен или часы ПЛК не установлены (`MQTT_ERR_NO_CLOCK`) | `xEnable` и часы есть → `Connecting` |
| `Connecting` | перед `Connect` в `stBroker` пишется завещание: топик `…/status/connection`, текст `offline`/`lwt` со временем подключения | `IsConnected()` → `Connected`; `Connect()` = FALSE или нет связи за `tConnectTimeout` (10 с) → `Backoff` |
| `Connected` | рождение `online`/`birth` (`source`, `sw_version`, `period_ms`); принято клиентом → `xReady` | связь пропала → `Backoff`; `xEnable` = FALSE → `Closing` |
| `Backoff` | пауза `tBackoff`: от `tBackoffMin` (1 с), удваивается до `tBackoffMax` (60 с); после `tStable` (30 с) устойчивой связи снова минимальна | пауза прошла → `Connecting` |
| `Closing` | опубликовано `offline`/`shutdown` | следующий вызов: `Disconnect()` → `Disabled` |

Рождение запускает у телеметрии и тревог контрольную публикацию и снимок. Сообщения состояния —
[data_schema.md, раздел 6](data_schema.md#6-состояние-узла) и `schema/status.schema.json` (обязательные
поля `schema_version`, `ts`, `node`, `state`, `reason`), QoS 1, retain.

Сводный статус `eNe107` (в духе NAMUR NE 107, для HMI и метрики качества):

| Статус | Когда |
|---|---|
| Good | связь есть, публикации проходят |
| MaintenanceRequired | связь есть, но за окно `tDegradeWindow` клиент отклонял публикации (очередь) — `xDegraded` |
| OutOfSpecification | связи нет, идут повторы |
| CheckFunction | обмен выключен, нет часов или первое подключение ещё не состоялось |
| Failure | подряд неудачных подключений не меньше `uiFailThreshold` (3) |

Счётчики: `udiConnects`, `udiDisconnects` (потери установленной связи), `udiConnectFailures`,
`uiConsecutiveFailures`; `diLastError` — `GVL_Const.MQTT_ERR_*` (−1…−5) или код библиотеки (больше 0).

## Адаптер I_MqttClient

Логика работает только через `I_MqttClient`; методы неблокирующие, результат подключения виден по
`IsConnected()` в следующих циклах:

| Метод | Смысл |
|---|---|
| `Cycle()` | обслуживание клиента: один раз за цикл до остальных методов |
| `Connect(stCfg)` | запросить подключение с параметрами `ST_MqttBrokerCfg` (включая LWT); TRUE — запрос принят |
| `IsConnected()` | CONNACK получен, связь не потеряна |
| `Disconnect()` | разорвать соединение |
| `Publish(sTopic, eQos, xRetain, sPayload)` | поставить сообщение в очередь; TRUE — клиент его принял и скопировал, FALSE — повторить позже |
| `Subscribe(sTopicFilter, eQos)` | подписаться (допустимы `+` и `#`) |
| `Receive(sTopic, sPayload, xTruncated, xRetained)` | забрать одно принятое сообщение; `xTruncated` — не поместилось в буфер, `xRetained` — пришло с retain |
| `LastError()` | 0 — нет; отрицательные — `MQTT_ERR_*`; положительные — коды библиотеки |

Реализации:

- `FB_MqttClientNone` (`src/`) — без транспорта: `Connect`, `Publish`, `Subscribe` возвращают FALSE,
  `LastError()` = `MQTT_ERR_NO_TRANSPORT`. Используется, пока `PRG_Iiot.itfClientOverride` не задан.
- `FB_MqttClientFake` (`tests/`) — подменный клиент тестов: записывает публикации, отдаёт заданные
  входящие сообщения, имитирует отказы подключения, очереди и подписки.
- `FB_MqttClientSdMqtt` (`adapters/sd_mqtt_1_0/`) — на библиотеку CODESYS-MQTT 1.0.0.0 (Stefan Dreyer,
  MIT): обработчик `HANDLE_MQTT`, пул из 8 `MQTTPublish` (библиотека требует не менять топик и текст до
  `done` и запускает публикацию по фронту), `MQTTSubscribe`. **Не компилировался с библиотекой**: на
  3.5.17.30 у неё нет зависимостей, поэтому файл лежит вне `src/` и в сборку не входит. Известные
  ограничения версии 1.0.0.0 (по её объявлениям): логин и пароль брокера через входы не передаются —
  адаптер отклоняет `Connect` с непустым `sUser` (`MQTT_ERR_AUTH_UNSUPPORTED`), а не подключается без
  пароля; завещание библиотека строит сама из ClientID (текст до 30 символов), `offline`/`lwt` по схеме
  с ней не получить; флаг retain принятых сообщений не виден — проверка `retained` не срабатывает.
  Подключение адаптера — [MANUAL_STEPS.md, раздел 9](MANUAL_STEPS.md#9-библиотека-codesys-mqtt).

Другой клиент (вендорская библиотека MQTT ПЛК210, CODESYS IIoT Libraries SL, своя реализация на
TCP) подключается так же: ФБ с `IMPLEMENTS I_MqttClient` и присваивание
`PRG_Iiot.itfClientOverride := fbMyClient;` до первого вызова `PRG_Iiot`.

## PRG_Iiot и теги флагмана

Порядок за цикл:

1. Первый вызов: копирование таблиц `GVL_IiotMap` (метрики, тревоги, белый список) в рабочие массивы.
2. Клиент: `itfClientOverride` или `FB_MqttClientNone`; `Cycle()`.
3. Время: `F_IiotNow()` — монотонное; `SysTimeRtcHighResGet` — UTC в мс; `F_IiotClockValid` — часы в
   диапазоне схемы (2020…2100), иначе обмен не начинается (`MQTT_ERR_NO_CLOCK`).
4. `FB_IiotKnsMap.FillPoints` и `FillAlarmWords` — значения, качество и слова тревог из
   `GVL_Devices.fb<TAG>`, `GVL_IO` и `GVL_Station` (станция, регулятор LIC101); метрики узла `PLC1`
   (uptime, переподключения, очередь, отброшено, принятые и отклонённые команды).
5. `FB_MqttDiag`, затем `FB_MqttTelemetry` и `FB_MqttAlarms` (публикуют только при `xReady`).
6. `FB_MqttCommands`; прошедшая команда пишется в `GVL_Hmi.st<TAG>Cmd` или `GVL_Station` в том же цикле.
7. Состояние — в `GVL_Iiot.stIiotSts`.

Во флагмане `PRG_Iiot` вызывается в той же задаче после `PRG_Devices`: значения устройств — текущего
цикла, а команда из `GVL_Hmi` обрабатывается устройством в следующем цикле, как команда с HMI.
Встраивание — [MANUAL_STEPS.md, раздел 11](MANUAL_STEPS.md#11-встраивание-во-флагман).

## Таблицы из схемы данных

`tools_project/gen_plc_iiot.py` генерирует из `schema/` (каталог метрик, белый список команд, перечень
тревог, теги флагмана):

- `src/GVLs/Generated/GVL_IiotMap.gvl.st` — константы `POINT_COUNT` (139), `RULE_COUNT` (86),
  `ALARM_COUNT` (88), индексы `PT_<DEVICE>_<METRIC>` и таблицы `POINT_CFG`, `RULE_CFG`, `ALARM_CFG`;
- `flagship/src/POUs/Iiot/FB_IiotKnsMap/` — методы `FillPoints`, `FillAlarmWords` (пути `plc_path`
  каталога), `ApplyCommand` (пути белого списка в `GVL_Hmi`), `DeviceCmdState` (`uiCmdSeq`, `eCmdResult`).
  Массив короче перечня методы `Fill*` не заполняют (проверка `LOWER_BOUND`/`UPPER_BOUND`).

Файлы руками не правятся: `python tools_project/gen_plc_iiot.py` после изменения `schema/`,
`--check` — проверка актуальности (тест `test_generated_plc_tables_are_up_to_date`, CI).

## Привязка к флагману

Флагман (КНС-1 на библиотеке plc-process-lib, репозиторий kns-pump-station) — отдельный проект. Раньше
ПЛК-часть собиралась здесь вместе с заглушкой его типов и списков (`KnsShim`); теперь заглушки нет, а
привязка ссылается на настоящие символы флагмана:

| Что | Путь во флагмане | Доступ OPC UA (правила символов флагмана) |
|---|---|---|
| значения и состояние устройств | `GVL_Devices.fb<TAG>.stSts.*`, выходы `xRunning`, `xValue`, `xValid` (`PL.FB_*`) | чтение |
| команды устройствам | `GVL_Hmi.st<TAG>Cmd.*` (`PL.ST_*Cmd`) | запись |
| сигналы без ФБ | `GVL_IO.xK1` (реле «Общая авария», в норме под напряжением), `GVL_IO.uiP10n_FCODE` | чтение |
| станция KNS1 | `GVL_Station.stStationSts.*` (`ST_StationSts`, DESIGN 3.1 флагмана) | чтение |
| команды станции | `GVL_Station.stStationCmd.*` (`ST_StationCmd`) | запись |
| регулятор уровня LIC101 | `GVL_Station.fbLIC101.stSts.*` (`PL.ST_PidSts`), команды `GVL_Station.stLIC101Cmd.stCommon.*` | чтение / запись |
| константы | `PL.GVL_Const.MOT_FLT_COMM_LOSS`, `MOT_WRN_COMM_LOSS`, `PL.E_DeviceMode.OutOfService` | — |

Интерфейс флагмана снят в `schema/source/` командой `python tools_project/flagship_snapshot.py`
(читает `git show <rev>:<путь>`, рабочую копию флагмана не трогает): теги и тревоги устройств iolistgen,
теги и тревоги станции, объявления списков, типы и правила символьной конфигурации; коммит —
`schema/source/flagship_symbols.json`. По снимку `tests_stack/test_flagship_binding.py` проверяет
каждый путь каталога, белого списка, узлов Telegraf, тегов эмулятора и сгенерированного ST: переменная
есть, выгружается в символы, тип совпадает, а писать можно только в структуры команд.

Компиляцию привязки проверяет только CODESYS во флагмане: здесь её типы `PL.*` и глобальные списки
недоступны. Шаги встраивания — [MANUAL_STEPS.md, раздел 11](MANUAL_STEPS.md#11-встраивание-во-флагман).

## Настройки и состояние

`GVL_Iiot.stIiotCfg` (`ST_IiotCfg`) задаёт наладчик в IDE; по OPC UA — только чтение
(`{attribute 'symbol' := 'read'}`):

| Поле | По умолчанию | Смысл |
|---|---|---|
| `xEnable` | FALSE | обмен MQTT |
| `xCommandsEnable` | FALSE | приём команд |
| `sSite`, `sArea`, `sUnit` | `vodokanal`, `kns1`, `station` | префикс топиков |
| `sNode` | `PLC1` | узел ПЛК: `status/connection` и метрики `PLC1/*` |
| `sSwVersion` | `0.1.0` | `sw_version` в рождении |
| `tTelemetryPeriod` | 60 с | контрольная публикация, `period_ms` |
| `stBroker` | — | `sHost`, `uiPort` (1883), `xTls`, `sClientId` (`kns1-plc1`), `sUser`, `sPassword`, `tKeepAlive`, `xCleanSession`; поля завещания заполняет `FB_MqttDiag` |

`sPassword` помечен `{attribute 'symbol' := 'none'}`: в символы OPC UA не выгружается (проверено по
файлу символов, [MANUAL_STEPS.md, раздел 10](MANUAL_STEPS.md#10-символьная-конфигурация-для-opc-ua)).
Пароль и логин в git не хранятся: на стенде они в `.env`, в ПЛК задаются при наладке.

`GVL_Iiot.stIiotSts` (`ST_IiotSts`, только чтение): `eConnState`, `eNe107`, счётчики подключений и
публикаций, `uiQueue`, `udiDropped`, `udiCmdAccepted`, `udiCmdRejected`, `eLastCmdReason`,
`diLastError`, `xClockValid`.

## Отличия и ограничения

- Зона нечувствительности: контракт — «больше» зоны, ST — строгое `>`; эмулятор
  (`emulator/iiot_emulator/telemetry.py`, `deadband_exceeded`) приведён к той же таблице истинности,
  включая NaN и бесконечность.
- События тревог восстанавливаются по словам тревог: переходы между публикациями сливаются (раздел
  «Тревоги»).
- Ответ на команду, не принятый клиентом, не повторяется.
- Адаптер CODESYS-MQTT не собран и не проверен на брокере; работа по сети, TLS и поведение при обрыве —
  после подключения настоящей библиотеки (раздел «Адаптер I_MqttClient»).
- Часы ПЛК должны синхронизироваться по NTP: без этого `ts` неверен, а команды получают `expired`.
- Привязка к флагману (`flagship/src/`) в CODESYS не компилировалась: её пути и типы сверены со снимком
  интерфейса флагмана, а сборка, тесты и живой обмен по OPC UA и MQTT — после встраивания
  ([MANUAL_STEPS.md, раздел 11](MANUAL_STEPS.md#11-встраивание-во-флагман)).
- Изменения ядра после прогона 16.10.2026 (номер тревоги `UDINT`, суффикс до 8 знаков, слово
  `wSuppressed`, команды станции, версия схемы 1.1) проверены RuSTy и iec_checker, но не в CODESYS.
