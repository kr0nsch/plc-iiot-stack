# Отчёт о тестировании

Результаты юнит-тестов CfUnit (coUnit 1.2.0.0) в CODESYS Control Win V3 и проверок без CODESYS.
Запись «проверено в CODESYS» появляется только после реального прогона. Раздел «Последний прогон
в CODESYS» обновляет `python tools/codesys/cds.py report` по итогам `cds.py test`
(`build/test-results.json`); правки внутри него вручную перезаписываются.

> **19.10.2026 — первый прогон после привязки к флагману.** Ядро: 85 тестов из 85 в 8 наборах (раздел
> ниже, коммит `5f01cd7`; по сравнению с 16.10.2026 удалён набор `FB_KnsShim_Test` вместе с заглушкой,
> добавлены `FB_IiotMap_Test` и тесты станции). Привязка `flagship/src/` здесь не собирается: она собрана и
> проверена во флагмане вместе с ядром и наборами `flagship/tests/` — раздел
> [«Встраивание во флагман и стенд против его рантайма»](#встраивание-во-флагман-и-стенд-против-его-рантайма).

<!-- cds:test-report:begin (раздел обновляет `python tools/codesys/cds.py report`) -->
## Последний прогон в CODESYS

Проверено в CODESYS 3.5.17.30 / CODESYS Control Win V3 (пользовательский процесс) — 2026-10-19 23:13:40. Итог: **все тесты пройдены**.

| Параметр | Значение |
|---|---|
| Дата прогона | 2026-10-19 23:13:40 |
| Коммит | 5f01cd7 |
| CODESYS | 3.5.17.30 (профиль `CODESYS V3.5 SP17 Patch 3`) |
| Устройство в проекте | CODESYS Control Win V3 (4096 / 0000 0001 / 3.5.17.30) |
| Рантайм | CODESYS Control Win V3 (пользовательский процесс) |
| Фреймворк тестов | coUnit (CfUnit) 1.2.0.0 |
| Сборка | ошибок 0, предупреждений 0 |
| Способ запуска | `python tools/codesys/cds.py test` |

| Набор | Тестов | Пройдено | Упало | Пропущено | Итог |
|---|---|---|---|---|---|
| `PRG_Tests.fbJsonBuilderTest` | 9 | 9 | 0 | 0 | пройдено |
| `PRG_Tests.fbJsonFlatParserTest` | 13 | 13 | 0 | 0 | пройдено |
| `PRG_Tests.fbIiotFunctionsTest` | 12 | 12 | 0 | 0 | пройдено |
| `PRG_Tests.fbMqttTelemetryTest` | 11 | 11 | 0 | 0 | пройдено |
| `PRG_Tests.fbMqttAlarmsTest` | 11 | 11 | 0 | 0 | пройдено |
| `PRG_Tests.fbMqttCommandsTest` | 15 | 15 | 0 | 0 | пройдено |
| `PRG_Tests.fbMqttDiagTest` | 12 | 12 | 0 | 0 | пройдено |
| `PRG_Tests.fbIiotMapTest` | 2 | 2 | 0 | 0 | пройдено |
| **Всего** | 85 | 85 | 0 | 0 | **пройдено** |

### Результаты тестов

| Набор | Тест | Итог |
|---|---|---|
| `PRG_Tests.fbJsonBuilderTest` | `BuildsFlatObjectWithAllTypes` | пройден |
| `PRG_Tests.fbJsonBuilderTest` | `EmptyObjectAndRestart` | пройден |
| `PRG_Tests.fbJsonBuilderTest` | `EscapesSpecialCharacters` | пройден |
| `PRG_Tests.fbJsonBuilderTest` | `RealFormattingRoundsAndTrimsZeros` | пройден |
| `PRG_Tests.fbJsonBuilderTest` | `RealFromRealIsRoundedLikeTheValueShown` | пройден |
| `PRG_Tests.fbJsonBuilderTest` | `NotFiniteBecomesNull` | пройден |
| `PRG_Tests.fbJsonBuilderTest` | `IntExtremes` | пройден |
| `PRG_Tests.fbJsonBuilderTest` | `OverflowIsReportedNotTruncatedSilently` | пройден |
| `PRG_Tests.fbJsonBuilderTest` | `BufferHoldsExactlyItsSize` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `ParsesFlatObjectWithAllTypes` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `TracksIntegerLiterals` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `AcceptsWhitespaceAndEmptyObject` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `RejectsNestedObjectsAndArrays` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `RejectsDuplicateKeys` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `RejectsSyntaxErrors` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `RejectsTrailingCharacters` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `ValidatesNumberGrammarAndRange` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `DecodesEscapes` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `RejectsRawControlCharacters` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `LimitsKeyAndValueLength` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `LimitsFieldCount` | пройден |
| `PRG_Tests.fbJsonFlatParserTest` | `FailedParseClearsPreviousFields` | пройден |
| `PRG_Tests.fbIiotFunctionsTest` | `DeadbandIsStrictlyGreater` | пройден |
| `PRG_Tests.fbIiotFunctionsTest` | `ZeroNegativeOrNanDeadbandMeansAnyChange` | пройден |
| `PRG_Tests.fbIiotFunctionsTest` | `NonFiniteTransitionsAreChanges` | пройден |
| `PRG_Tests.fbIiotFunctionsTest` | `QualityPerSchema` | пройден |
| `PRG_Tests.fbIiotFunctionsTest` | `CommandNamesKindsAndTexts` | пройден |
| `PRG_Tests.fbIiotFunctionsTest` | `SchemaMajorParsing` | пройден |
| `PRG_Tests.fbIiotFunctionsTest` | `CmdIdNameAndOriginPatterns` | пройден |
| `PRG_Tests.fbIiotFunctionsTest` | `AlarmStateFromWords` | пройден |
| `PRG_Tests.fbIiotFunctionsTest` | `AlarmReasonByTransition` | пройден |
| `PRG_Tests.fbIiotFunctionsTest` | `TopicJoinAndLimit` | пройден |
| `PRG_Tests.fbIiotFunctionsTest` | `ClockValidityRange` | пройден |
| `PRG_Tests.fbIiotFunctionsTest` | `NowIsMonotonic` | пройден |
| `PRG_Tests.fbMqttTelemetryTest` | `PublishesAllAfterBirthWithExactJson` | пройден |
| `PRG_Tests.fbMqttTelemetryTest` | `WaitsForBirthAndClock` | пройден |
| `PRG_Tests.fbMqttTelemetryTest` | `DeadbandAndMinInterval` | пройден |
| `PRG_Tests.fbMqttTelemetryTest` | `QualityChangeIsImmediate` | пройден |
| `PRG_Tests.fbMqttTelemetryTest` | `IntegerAnyChangeAndPeriodicOnly` | пройден |
| `PRG_Tests.fbMqttTelemetryTest` | `PeriodRepublishesAll` | пройден |
| `PRG_Tests.fbMqttTelemetryTest` | `BudgetLimitsPublishesPerCallRoundRobin` | пройден |
| `PRG_Tests.fbMqttTelemetryTest` | `RepublishesAllAfterReconnect` | пройден |
| `PRG_Tests.fbMqttTelemetryTest` | `ClientRefusalIsCountedAndRetried` | пройден |
| `PRG_Tests.fbMqttTelemetryTest` | `NegativeAndLargeValues` | пройден |
| `PRG_Tests.fbMqttTelemetryTest` | `NotFiniteValueSendsLastFiniteAsBad` | пройден |
| `PRG_Tests.fbMqttAlarmsTest` | `SnapshotAfterBirthExactJson` | пройден |
| `PRG_Tests.fbMqttAlarmsTest` | `EventsFollowWordChanges` | пройден |
| `PRG_Tests.fbMqttAlarmsTest` | `ReturnUnackedThenAck` | пройден |
| `PRG_Tests.fbMqttAlarmsTest` | `ShelvedAndOutOfService` | пройден |
| `PRG_Tests.fbMqttAlarmsTest` | `SnapshotAfterReconnectShowsCurrentState` | пройден |
| `PRG_Tests.fbMqttAlarmsTest` | `ReconnectRepeatsLastEventWithItsTs` | пройден |
| `PRG_Tests.fbMqttAlarmsTest` | `ChangeWhileOfflineIsEventAfterReconnect` | пройден |
| `PRG_Tests.fbMqttAlarmsTest` | `BudgetAndDisabledPriority` | пройден |
| `PRG_Tests.fbMqttAlarmsTest` | `WordsOutOfTableMeanNormal` | пройден |
| `PRG_Tests.fbMqttAlarmsTest` | `StationAlarmIdAndLongSuffix` | пройден |
| `PRG_Tests.fbMqttAlarmsTest` | `SuppressedByDesignFromWords` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `SubscribesToCommandTopicsAndResubscribes` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `AcceptedStartWaitsForDeviceThenOk` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `DeviceRejectedCarriesCmdResult` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `DeviceSilenceIsTimeout` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `SpeedSetpointIsOkAfterWrite` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `MissingArmMeansTimeout` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `RejectsRetainedCommand` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `RejectsInvalidPayloads` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `RejectsUnsupportedVersionAndTopicMismatch` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `RejectsNotWhitelisted` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `RejectsOutOfRange` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `RejectsExpired` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `RejectsDuplicateIncludingRejectedIds` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `RateLimitTenPerTenSeconds` | пройден |
| `PRG_Tests.fbMqttCommandsTest` | `DropsWithoutAckWhenNoCmdId` | пройден |
| `PRG_Tests.fbMqttDiagTest` | `DisabledIsCheckFunctionWithoutConnect` | пройден |
| `PRG_Tests.fbMqttDiagTest` | `ConnectSetsLwtAndPublishesBirth` | пройден |
| `PRG_Tests.fbMqttDiagTest` | `BirthRefusedMeansNotReady` | пройден |
| `PRG_Tests.fbMqttDiagTest` | `NoClockNoConnect` | пройден |
| `PRG_Tests.fbMqttDiagTest` | `ConnectTimeoutGoesToBackoff` | пройден |
| `PRG_Tests.fbMqttDiagTest` | `BackoffDoublesUpToMaximum` | пройден |
| `PRG_Tests.fbMqttDiagTest` | `RejectedConnectUsesClientErrorCode` | пройден |
| `PRG_Tests.fbMqttDiagTest` | `FailureAfterThresholdAndResetAfterStableLink` | пройден |
| `PRG_Tests.fbMqttDiagTest` | `ConnectionLossCountsAndReconnects` | пройден |
| `PRG_Tests.fbMqttDiagTest` | `DegradedWhenPublishFailuresGrow` | пройден |
| `PRG_Tests.fbMqttDiagTest` | `DisableWhileConnectedPublishesShutdown` | пройден |
| `PRG_Tests.fbMqttDiagTest` | `TimeGoingBackwardsRestartsTimeout` | пройден |
| `PRG_Tests.fbIiotMapTest` | `MapTablesFollowSchema` | пройден |
| `PRG_Tests.fbIiotMapTest` | `StationRowsFollowFlagship` | пройден |

### Упавшие тесты

_Нет._

Машиночитаемые результаты: `build/test-results.json`, `build/junit.xml` (не в git).
<!-- cds:test-report:end -->

## Что проверяют тесты

Наборы coUnit в `tests/` (8 наборов, 85 тестов) и `flagship/tests/` (1 набор, 5 тестов; выполняется только во
флагмане). Логика MQTT проверяется с подменным
клиентом `FB_MqttClientFake` (публикации, входящие сообщения, отказы подключения и очереди); ожидаемые
сообщения — точные строки JSON по [data_schema.md](data_schema.md).

| Набор | Тест | Что проверяет |
|---|---|---|
| `FB_JsonBuilder_Test` | `BuildsFlatObjectWithAllTypes` | объект со строкой, целым, логическим, null и числом — точный текст |
| `FB_JsonBuilder_Test` | `EmptyObjectAndRestart` | пустой объект; Begin очищает предыдущий текст |
| `FB_JsonBuilder_Test` | `EscapesSpecialCharacters` | экранирование кавычки, обратной косой черты и управляющих символов |
| `FB_JsonBuilder_Test` | `RealFormattingRoundsAndTrimsZeros` | числа: округление до знаков, без хвостовых нулей, -0 как 0, предел знаков |
| `FB_JsonBuilder_Test` | `RealFromRealIsRoundedLikeTheValueShown` | REAL 2.35 (в двоичном виде 2.3499999) с тремя знаками — 2.35 |
| `FB_JsonBuilder_Test` | `NotFiniteBecomesNull` | NaN, бесконечность и слишком большие числа пишутся как null |
| `FB_JsonBuilder_Test` | `IntExtremes` | целые: 0, максимум и минимум LINT, отметка времени в мс |
| `FB_JsonBuilder_Test` | `OverflowIsReportedNotTruncatedSilently` | переполнение буфера: xOverflow, Finish = FALSE, длина не больше буфера |
| `FB_JsonBuilder_Test` | `BufferHoldsExactlyItsSize` | объект ровно на размер буфера — полный, на байт больше — переполнение |
| `FB_JsonFlatParser_Test` | `ParsesFlatObjectWithAllTypes` | строка, число с порядком, true, false, null; поиск по ключу, ключ по номеру |
| `FB_JsonFlatParser_Test` | `TracksIntegerLiterals` | целое JSON — без дробной части и порядка: 1792137621000 — да, 1.0 и 1e3 — нет |
| `FB_JsonFlatParser_Test` | `AcceptsWhitespaceAndEmptyObject` | пробелы, табуляции и переводы строк между токенами; пустой объект |
| `FB_JsonFlatParser_Test` | `RejectsNestedObjectsAndArrays` | вложенный объект и массив — Nested |
| `FB_JsonFlatParser_Test` | `RejectsDuplicateKeys` | повторяющийся ключ — Duplicate (неоднозначная команда) |
| `FB_JsonFlatParser_Test` | `RejectsSyntaxErrors` | пустой вход, не объект, незакрытый объект, нет двоеточия, лишняя запятая, ключ без кавычек |
| `FB_JsonFlatParser_Test` | `RejectsTrailingCharacters` | символы после объекта — Trailing с позицией |
| `FB_JsonFlatParser_Test` | `ValidatesNumberGrammarAndRange` | числа: ведущий ноль, точка без цифр, знак без цифр, порядок без цифр, вне REAL, много цифр |
| `FB_JsonFlatParser_Test` | `DecodesEscapes` | Escape-последовательности JSON; код вне ASCII и неизвестные — BadEscape |
| `FB_JsonFlatParser_Test` | `RejectsRawControlCharacters` | управляющий символ внутри строки без экранирования — Syntax |
| `FB_JsonFlatParser_Test` | `LimitsKeyAndValueLength` | ключ до 31 и строка до 64 символов; длиннее — KeyTooLong, ValueTooLong |
| `FB_JsonFlatParser_Test` | `LimitsFieldCount` | полей не больше 12; 13-е — TooManyFields |
| `FB_JsonFlatParser_Test` | `FailedParseClearsPreviousFields` | после неудачного разбора поля прошлого объекта не видны |
| `FB_IiotFunctions_Test` | `DeadbandIsStrictlyGreater` | зона нечувствительности: изменение ровно на зону — нет, больше — да |
| `FB_IiotFunctions_Test` | `ZeroNegativeOrNanDeadbandMeansAnyChange` | зона <= 0 или не число — любое изменение |
| `FB_IiotFunctions_Test` | `NonFiniteTransitionsAreChanges` | переход между числом и NaN/бесконечностью — изменение; два неконечных — нет |
| `FB_IiotFunctions_Test` | `QualityPerSchema` | качество по data_schema 3.2: F — bad; S, C — uncertain; Good, M — good или bad по xValid |
| `FB_IiotFunctions_Test` | `CommandNamesKindsAndTexts` | имена команд (enum схемы, с учётом регистра), вид value, тексты reason и cmd_result |
| `FB_IiotFunctions_Test` | `SchemaMajorParsing` | мажорная версия из MAJOR.MINOR; не по формату — -1 |
| `FB_IiotFunctions_Test` | `CmdIdNameAndOriginPatterns` | шаблоны схемы: cmd_id [A-Za-z0-9_-]{8,36}, устройство, команда, origin |
| `FB_IiotFunctions_Test` | `AlarmStateFromWords` | состояние тревоги по словам: OOS, подавлена логикой (старше «отложена»), отложена, активна/неквитирована, вернулась, норма |
| `FB_IiotFunctions_Test` | `AlarmReasonByTransition` | причина события по переходу состояний и для снимка |
| `FB_IiotFunctions_Test` | `TopicJoinAndLimit` | топик <префикс>/<хвост>; без префикса — хвост; длиннее 127 — пустая строка |
| `FB_IiotFunctions_Test` | `ClockValidityRange` | часы ПЛК пригодны для ts: 2020-01-01 .. 2100-01-01 UTC включительно |
| `FB_IiotFunctions_Test` | `NowIsMonotonic` | монотонное время: время с запуска больше нуля, повторный вызов не возвращает меньшее значение |
| `FB_MqttTelemetry_Test` | `PublishesAllAfterBirthWithExactJson` | после рождения узла — все метрики; точный JSON, QoS 1, retain |
| `FB_MqttTelemetry_Test` | `WaitsForBirthAndClock` | до рождения узла и без часов ПЛК — ничего; потом — всё |
| `FB_MqttTelemetry_Test` | `DeadbandAndMinInterval` | зона нечувствительности и не чаще раза в секунду на метрику |
| `FB_MqttTelemetry_Test` | `QualityChangeIsImmediate` | смена качества публикуется сразу, без ожидания интервала |
| `FB_MqttTelemetry_Test` | `IntegerAnyChangeAndPeriodicOnly` | целые — при любом изменении; время работы узла — только контрольно |
| `FB_MqttTelemetry_Test` | `PeriodRepublishesAll` | по истечении периода — все метрики, раньше — нет |
| `FB_MqttTelemetry_Test` | `BudgetLimitsPublishesPerCallRoundRobin` | не больше uiMaxPerCycle за вызов, остальные — в следующих, по кругу |
| `FB_MqttTelemetry_Test` | `RepublishesAllAfterReconnect` | связь пропала и вернулась с новым рождением — все метрики заново |
| `FB_MqttTelemetry_Test` | `ClientRefusalIsCountedAndRetried` | клиент не принял — udiFailed, метрики ждут и уходят позже |
| `FB_MqttTelemetry_Test` | `NegativeAndLargeValues` | отрицательное Analog и большой счётчик Integer — без потери знака и разрядов |
| `FB_MqttTelemetry_Test` | `NotFiniteValueSendsLastFiniteAsBad` | значение NaN — последнее конечное значение с quality bad (схема: value — число), конечное — снова good |
| `FB_MqttAlarms_Test` | `SnapshotAfterBirthExactJson` | после рождения узла — снимок всех тревог; точный JSON, QoS 1, retain |
| `FB_MqttAlarms_Test` | `EventsFollowWordChanges` | появление, квитирование, снятие: Activated, Acked, Cleared |
| `FB_MqttAlarms_Test` | `ReturnUnackedThenAck` | условие ушло без квитирования — RtnUnack/Cleared, затем квитирование — Normal/Acked |
| `FB_MqttAlarms_Test` | `ShelvedAndOutOfService` | отложена/возвращена и вывод устройства из работы: Shelved, Unshelved, OosOn |
| `FB_MqttAlarms_Test` | `SnapshotAfterReconnectShowsCurrentState` | после переподключения — текущее состояние повтором первой публикации с её ts, а не событие |
| `FB_MqttAlarms_Test` | `ReconnectRepeatsLastEventWithItsTs` | сработавшая тревога после переподключения — то же событие Activated с исходными ts и prev_state (в InfluxDB та же точка, не второе срабатывание) |
| `FB_MqttAlarms_Test` | `ChangeWhileOfflineIsEventAfterReconnect` | тревога сработала без связи — после переподключения событие с текущим ts |
| `FB_MqttAlarms_Test` | `BudgetAndDisabledPriority` | не больше uiMaxPerCycle за вызов; приоритет None — тревога пропускается |
| `FB_MqttAlarms_Test` | `WordsOutOfTableMeanNormal` | строка слов вне таблицы — тревога в норме, без выхода за массив |
| `FB_MqttAlarms_Test` | `StationAlarmIdAndLongSuffix` | тревога станции `KNS1.NOAUTO`: номер 100009 (больше UINT), суффикс из шести знаков, бит `slot − 1`, точный JSON |
| `FB_MqttAlarms_Test` | `SuppressedByDesignFromWords` | бит `wSuppressed` — состояние `SuppressedByDesign` и причины `Suppressed`/`Unsuppressed` |
| `FB_IiotMap_Test` | `MapTablesFollowSchema` | таблицы GVL_IiotMap совпадают со схемой данных: 139 метрик, 86 команд, 88 тревог |
| `FB_IiotMap_Test` | `StationRowsFollowFlagship` | строки станции и LIC101: метрики, команды станции, номер и бит тревоги станции, суффикс без обрезки |
| `FB_IiotKnsMap_Test` (во флагмане) | `MapReadsFlagshipVariables` | метрики и слова тревог — из настоящих переменных: `K1/general_alarm` = NOT `GVL_IO.xK1`, режим станции `Manual` — 2, слово тревог станции — последняя строка, LT101, LIC101, P101 |
| `FB_IiotKnsMap_Test` (во флагмане) | `CommandsGoToFlagshipCmdStructs` | принятая команда — в `GVL_Hmi.st<TAG>Cmd` (импульс `Start`, значение `SpeedSp`), `GVL_Station.stStationCmd`, `stLIC101Cmd`; строка вне таблицы — FALSE |
| `FB_IiotKnsMap_Test` (во флагмане) | `CmdStateReadsFlagshipCounters` | счётчик и результат команды: станция — `stStationSts.uiCmdSeq`, `eCmdResult` (`RejectedMode` — 2), LIC101 — `fbLIC101.stSts.stCommon`; неизвестное устройство — нули |
| `FB_IiotKnsMap_Test` (во флагмане) | `MapIgnoresTooSmallTable` | массивы меньше перечня — `FB_IiotKnsMap` ничего не пишет |
| `FB_IiotKnsMap_Test` (во флагмане) | `PrgIiotPublishesAndAppliesStationCommand` | `PRG_Iiot` с подменным клиентом в приложении флагмана: рождение, `K1/general_alarm` = 1, `KNS1/mode` = 1, очередь пуста; `KNS1/SetStepped` — `GVL_Station.stStationCmd.xSetStepped`, ответа нет до роста `uiCmdSeq`, затем `accepted`/`ok`; `V1/SetOos` — `not_whitelisted`; выключение — `offline`/`shutdown`; переменные флагмана восстановлены |
| `FB_MqttCommands_Test` | `SubscribesToCommandTopicsAndResubscribes` | подписка <site>/<area>/<unit>/+/cmd/+ с QoS 1; заново после переподключения |
| `FB_MqttCommands_Test` | `AcceptedStartWaitsForDeviceThenOk` | Start прошёл шлюз: stCmd, ответа нет до обработки устройством, затем ok |
| `FB_MqttCommands_Test` | `DeviceRejectedCarriesCmdResult` | устройство отказало — device_rejected и cmd_result по E_CmdResult |
| `FB_MqttCommands_Test` | `DeviceSilenceIsTimeout` | устройство не обработало команду за 3 с — timeout; новое сообщение ждёт |
| `FB_MqttCommands_Test` | `SpeedSetpointIsOkAfterWrite` | SpeedSp: ok сразу после записи (ФБ устройства значения не квитирует); границы 0 и 100 |
| `FB_MqttCommands_Test` | `MissingArmMeansTimeout` | команда прошла шлюз, но Arm() не вызван — ответ timeout в следующем вызове |
| `FB_MqttCommands_Test` | `RejectsRetainedCommand` | команда с флагом retain — retained |
| `FB_MqttCommands_Test` | `RejectsInvalidPayloads` | не по command.schema.json — invalid_payload: лишние поля, ts, origin, command, value |
| `FB_MqttCommands_Test` | `RejectsUnsupportedVersionAndTopicMismatch` | schema_version 2.0 — unsupported_version; команда не та, что в топике |
| `FB_MqttCommands_Test` | `RejectsNotWhitelisted` | пары (устройство, команда) нет в белом списке — not_whitelisted |
| `FB_MqttCommands_Test` | `RejectsOutOfRange` | SpeedSp вне 0..100 % — out_of_range |
| `FB_MqttCommands_Test` | `RejectsExpired` | ts дальше 30 с от часов ПЛК (в прошлое или будущее) или часов нет — expired |
| `FB_MqttCommands_Test` | `RejectsDuplicateIncludingRejectedIds` | повтор cmd_id среди последних 16 (и отклонённых тоже) — duplicate |
| `FB_MqttCommands_Test` | `RateLimitTenPerTenSeconds` | не больше 10 команд за 10 с — rate_limited; после окна — снова принимаются |
| `FB_MqttCommands_Test` | `DropsWithoutAckWhenNoCmdId` | не своя станция, не JSON, нет или неверный cmd_id, обрезано — без ответа |
| `FB_MqttDiag_Test` | `DisabledIsCheckFunctionWithoutConnect` | выключено: Disabled, статус C, подключений нет |
| `FB_MqttDiag_Test` | `ConnectSetsLwtAndPublishesBirth` | подключение: завещание offline/lwt, рождение online/birth (QoS 1, retain), xReady |
| `FB_MqttDiag_Test` | `BirthRefusedMeansNotReady` | рождение не принято клиентом — связь есть, но публиковать нельзя; повтор |
| `FB_MqttDiag_Test` | `NoClockNoConnect` | часы ПЛК не установлены: подключения нет, код -5, статус C |
| `FB_MqttDiag_Test` | `ConnectTimeoutGoesToBackoff` | нет CONNACK за tConnectTimeout — неудача, код -2, разрыв, пауза, статус S |
| `FB_MqttDiag_Test` | `BackoffDoublesUpToMaximum` | пауза между попытками: 1, 2, 4 с и дальше 4 с (tBackoffMax) |
| `FB_MqttDiag_Test` | `RejectedConnectUsesClientErrorCode` | Connect() отклонён: код ошибки клиента, без него — -3 |
| `FB_MqttDiag_Test` | `FailureAfterThresholdAndResetAfterStableLink` | три неудачи подряд — F; после tStable связи счётчик и пауза сбрасываются |
| `FB_MqttDiag_Test` | `ConnectionLossCountsAndReconnects` | потеря связи: разрыв, код -4, пауза 1 с, переподключение и новое рождение |
| `FB_MqttDiag_Test` | `DegradedWhenPublishFailuresGrow` | рост отказов публикаций за окно — M; нет роста — снова Good |
| `FB_MqttDiag_Test` | `DisableWhileConnectedPublishesShutdown` | выключение при связи: offline/shutdown, затем разрыв в следующем вызове |
| `FB_MqttDiag_Test` | `TimeGoingBackwardsRestartsTimeout` | время пошло назад — отсчёт тайм-аута заново, без зависания |

## Проверки без CODESYS

Итоги последнего прогона CI (ссылка на запуск GitHub Actions) или локального прогона.

| Проверка | Итог | Примечание |
|---|---|---|
| `ruff check`, `ruff format --check`, `mypy --strict`, `pytest` (корень) после проверки на флагмане | пройдено, 2026-10-19, локально | pytest без поднятого стенда: 864 пройдено, 16 пропущено (15 интеграционных тестов стенда и 1 тест только для POSIX); с локальным стендом на эмуляторе интеграционные — 15 из 15. Новые тесты: `test_flagship_embed.py` (8: встраивание на модели флагмана, типы узлов по снимку), узлы OPC UA делятся по входам Telegraf до 100 (6), переменная окружения важнее `.env` (1), все узлы OPC UA со статусом Good без пути MQTT (1, интеграционный) |
| `gen_plc_iiot.py --check`, `gen_config.py --check`, `flagship_snapshot.py --check` после проверки на флагмане | пройдено, 2026-10-19, локально | снимок снят с `main` флагмана `f750cea`; от `58fc169`, на котором выполнена проверка в CODESYS, он отличается только строками «Автор» в заголовках объектов |
| `tools/check/st_lint.py --strict` после проверки на флагмане | пройдено, 2026-10-19, локально | 510 файлов, в том числе `flagship/tests/`; 0 замечаний |
| iec_checker 0.4, `run_iec_checker.py --tests` после проверки на флагмане | пройдено, 2026-10-19, локально | 70 объектов; необоснованных 0, ошибок разбора 0, обоснованных 1177 |
| `ruff check`, `ruff format --check`, `mypy --strict`, `pytest` (корень) после привязки к флагману | пройдено, 2026-10-19, локально | pytest без поднятого стенда: 849 пройдено, 15 пропущено (14 интеграционных тестов стенда и 1 тест только для POSIX); с поднятым локальным стендом — 863 пройдено, 1 пропущен; в том числе `tests_stack/test_flagship_binding.py` (27 тестов: пути и права по снимку флагмана) и интеграционные с настоящими iec_checker и RuSTy |
| эмулятор `emulator/`: mypy, pytest | пройдено, 2026-10-19, локально | 101 тест, в том числе станция KNS1 и LIC101 (`test_station.py`) |
| отчёт `report/`: mypy, pytest | пройдено, 2026-10-19, локально | 89 пройдено, 1 пропущен без стенда; на локальном стенде — 90 из 90 |
| `gen_plc_iiot.py --check`, `gen_config.py --check`, `flagship_snapshot.py --check` | пройдено, 2026-10-19, локально | снимок снят с `main` (`0fedf61`); интерфейс тот же у `505ce14` и у более позднего `6459c7c` |
| `tools/check/st_lint.py --strict` | пройдено, 2026-10-19, локально | 496 файлов `src/`, `tests/`, `flagship/src/`, `adapters/sd_mqtt_1_0/src/`, 0 замечаний |
| iec_checker 0.4, `run_iec_checker.py --tests` | пройдено, 2026-10-19, локально | 70 объектов; необоснованных 0, ошибок разбора 0, неиспользованных обоснований 0, обоснованных 1177 |
| RuSTy 1.0.6, `run_rusty.py` (необязательно) | 293 ошибки, 15 предупреждений, 2026-10-19 | те же расширения CODESYS, что 16.10.2026; от изменений ядра — ни одной |
| `ruff check`, `ruff format --check`, `mypy --strict`, `pytest` (корень) | пройдено, 2026-10-16, локально | pytest без поднятого стенда: 804 пройдено, 13 пропущено (12 интеграционных тестов стенда и 1 тест только для POSIX); отключённых тестов шаблона нет; интеграционные с настоящими iec_checker и RuSTy выполнялись, в том числе `test_integration_repository_sources` (исходники проекта с его обоснованиями) |
| эмулятор `emulator/`: mypy, pytest | пройдено, 2026-10-16, локально | 93 теста |
| отчёт `report/`: mypy, pytest | пройдено, 2026-10-16, локально | 89 пройдено, 1 пропущен без стенда (`test_live_influx.py`); на локальном стенде — 90 из 90 |
| `tools_project/gen_plc_iiot.py --check`, `gen_config.py --check` | пройдено, 2026-10-16, локально | таблицы ПЛК, узлы OPC UA, тексты тревог, дашборды и таблицы `data_schema.md` совпадают со `schema/` |
| `tools/check/st_lint.py --strict` | пройдено, 2026-10-16, локально | 506 файлов `src/` и `tests/`, 0 замечаний; адаптер `adapters/sd_mqtt_1_0` — 20 файлов, 0 замечаний |
| iec_checker 0.4, `tools/check/run_iec_checker.py --tests` | пройдено, 2026-10-16, локально | 94 объекта `src/` и `tests/`; необоснованных 0, ошибок разбора 0, неиспользованных обоснований 0, обоснованных 1418 — разбор в [STATIC_ANALYSIS.md](STATIC_ANALYSIS.md) |
| RuSTy 1.0.6 (локально, `run_rusty.py`, необязательно) | 314 ошибок, 19 предупреждений | расширения CODESYS, которых нет в RuSTy (`s[i]`, `ARRAY[*]`, параметры метода-помощника `Run` наборов) и в прокладках шаблона — [STATIC_ANALYSIS.md](STATIC_ANALYSIS.md#rusty-plc---check) |

## Встраивание во флагман и стенд против его рантайма

19.10.2026, CODESYS 3.5.17.30, CODESYS Control Win V3 (пользовательский процесс). Флагман — своя рабочая
копия kns-pump-station, `main` `58fc169`; встраивание — `python tools_project/flagship_embed.py --repo <копия>`:
ядро, привязка, раздел «IIoT» в `GVL_Const`, `PRG_Iiot` в `MainTask`, правило символов `GVL_Iiot`, наборы
тестов (правки настроек флагмана — [flagship-patches/](flagship-patches/README.md)). plc-process-lib 1.0.0.0 и
iolistgen — из соседних репозиториев (`PL_REPO`, `IOLISTGEN_REPO`).

| Проверка | Итог | Подробности |
|---|---|---|
| `cds.py build` флагмана (приложение режима normal) | 0 ошибок, 0 предупреждений | `PRG_Iiot` в `MainTask` после `PRG_Devices`, сборка всего приложения (rebuild) |
| `cds.py test` флагмана | 423 из 423, 38 наборов | 333 теста флагмана (29 наборов) и 90 этого репозитория в `GVL_TestsIiot`: ядро — 85 (8 наборов, те же, что в разделе «Последний прогон»), `FB_IiotKnsMap_Test` — 5; сборка тестового приложения — 0 ошибок, 0 предупреждений |
| `sim.py start` флагмана: символы сборки `sim`, загрузка, «Старт» | приложение в работе | `GVL_Iiot: Read — 2` по правилу `GVL_Iiot`; у `ST_MqttBrokerCfg` в символах 10 полей из 11, `sPassword` нет. С правилами без `GVL_Iiot` (`symbol_config.py --rules`) список в символы не попал, а сверка прошла — правило нужно |
| `tools_project/opcua_live_check.py` | 133 узла из 133 Good, расхождений 0 | вход Basic256Sha256 / SignAndEncrypt по имени и паролю (клиент сценариев флагмана в доверенных); пространство имён 4 `CODESYSSPV3/3S/IecVarAccess`, устройство `CODESYS Control Win V3`, префикс `\|var\|CODESYS Control Win V3.`; пределы сервера — 100 узлов (`MaxNodesPerRead`, `MaxNodesPerWrite`, `MaxNodesPerRegisterNodes`, `MaxNodesPerBrowse`, `MaxMonitoredItemsPerCall`); типы — как в снимке: Int16 — 64 (все перечисления), Boolean — 19, Float — 29, UInt16 — 13, UInt32 — 8; `GVL_IO.xK1 = TRUE`; `GVL_Iiot.stIiotSts`: `eConnState` 0 (Disabled), `eNe107` 3 (C), `xClockValid` TRUE — `PRG_Iiot` работает в задаче; узел `sPassword` — `BadNodeIdUnknown` |
| `opcua_live_check.py --commands` | 4 команды из 4 | запись `xSetAuto`, затем `xSetManual` в `GVL_Station.stStationCmd` и `stLIC101Cmd.stCommon`: `uiCmdSeq` станции и LIC101 — 0 → 1 → 2, `eCmdResult` = 1 (Accepted) каждый раз, режим 2 → 1 → 2 (возвращён) |
| локальный стенд без Docker против рантайма (Telegraf 1.39.3, InfluxDB 2.9.1) | 133 узла из 133 в InfluxDB, все `StatusGood` | вход — из окружения запуска, не из `.env`; первое подключение — сертификат Telegraf в карантине рантайма (`connection failed: EOF`), после переноса в доверенные и перезапуска рантайма — вход. Один вход Telegraf на 133 узла сервер отклонял (`StatusBadTooManyOperations` на RegisterNodes) — исправлено: два входа (67 + 66). `K1/general_alarm` (opcua) = 0 при `xK1 = TRUE` — инверсия верна; 1596 точек за 2 мин при опросе раз в 5 с |
| `python -m pytest -m stack tests_stack -k opcua_catalog_nodes_status_good` (`IIOT_STACK=1`) | 1 из 1 | тот же стенд против рантайма; весь `-m stack` без `IIOT_STACK`: 6 пройдено, 9 пропущено (им нужен узел PLC1 по MQTT) |

Не проверено: публикация из ПЛК и команды по MQTT (`send_command.py`) — клиента MQTT, который собирается на
3.5.17.30, нет, `PRG_Iiot` работает с клиентом без транспорта (`xEnable = FALSE`); ответ на `SpeedSp` (устройство
не увеличивает счётчик команд); стенд в docker compose против рантайма (Docker на машине нет); ПЛК210.

## Стенд: сквозной путь данных

| Проверка | Итог | Примечание |
|---|---|---|
| локальный стенд без Docker (`tools_project/local_stack.ps1 start -Emulator`): InfluxDB 2.9.1, Telegraf 1.39.3, Grafana 12.4.12 (сборки для Windows), брокер amqtt 0.12.1, эмулятор | пройдено, 2026-10-16 | данные на дашбордах через 5 с после запуска эмулятора; отличия от compose — [ARCHITECTURE.md](ARCHITECTURE.md#10-локальный-стенд-без-docker) |
| `python -m pytest -m stack tests_stack` на локальном стенде | 12 из 12, 2026-10-16 | все 115 метрик каталога по MQTT, путь OPC UA (115 узлов, `StatusGood`), ACL, фильтр мажорной версии, завещание (LWT), аудит команд, отказ `not_whitelisted` сквозь базу, `out_of_range`, принятая команда, задача прореживания (среднее, взвешенное по времени, против расчёта по сырым точкам) |
| `tools_project/check_dashboards.py` на локальном стенде | 42 из 42, 2026-10-16 | без отказов — 39–41 панель с данными и 1–3 пустых списка отклонений (сколько отклонений есть в данный момент); с отказами, включёнными через OPC UA (`Simulation.Inject`), данные у всех 42 |
| локальный стенд с нуля после привязки к флагману, `python -m pytest -m stack tests_stack` | 14 из 14, 2026-10-19 | добавлены проверки: все 133 узла OPC UA каталога (станция KNS1, регулятор LIC101), одинаковое значение `K1/general_alarm` по MQTT и OPC UA, команда станции `KNS1/SetLevelPid` — `accepted`; отдельно — тревога `KNS1.NOAUTO` (номер 100009) дошла до InfluxDB с русским текстом |
| `tools_project/check_dashboards.py`, 2026-10-19 | 42 из 42 | 38–39 панелей с данными (два прогона), остальные — пустые списки отклонений, ошибок нет |
| локальный стенд с эмулятором после разбиения узлов OPC UA на два входа Telegraf, `python -m pytest -m stack tests_stack` | 15 из 15, 2026-10-19 | добавлен тест «все узлы каталога по OPC UA со статусом Good без пути MQTT»; путь OPC UA эмулятора — два сеанса Telegraf |
| стенд против флагмана в CODESYS (OPC UA, MANUAL_STEPS.md, раздел 12) | пройдено, 2026-10-19 | 133 узла из 133 в InfluxDB со статусом `StatusGood`, вход Basic256Sha256 по имени, доверие сертификату Telegraf, инверсия K1 — раздел [«Встраивание во флагман и стенд против его рантайма»](#встраивание-во-флагман-и-стенд-против-его-рантайма) |
| локальный стенд с нуля, Telegraf через прокси с пределом 100 неподтверждённых сообщений (как `max_inflight_messages` Mosquitto), тесты через 7 с после рождения эмулятора, `python -m pytest -m stack tests_stack` | до исправления — 1 отказ, после — 15 из 15, 2026-10-20 | так воспроизведён отказ CI: по MQTT в базе первые 100 метрик каталога из 139, хвост приходит со вторым сбросом Telegraf, а тесты запускались раньше. Тесты полного каталога и `K1/general_alarm` по обоим путям теперь ждут до 75 с (контрольный период и два сброса). Telegraf запускается со строгой подстановкой окружения явно (`--strict-env-handling`) — предупреждение 1.38+ больше не выводится |
| `make demo DEV=1`, `make test-stack`, отчёт по данным стенда в docker compose | пройдено, 2026-10-20, CI (запуск [39337438212](https://github.com/kr0nsch/plc-iiot-stack/actions/runs/39337438212)) | задание `stack` в `.github/workflows/ci.yml` (Linux, GitHub Actions): `make demo DEV=1` с нуля за 40 с, включая загрузку образов и сборку эмулятора; интеграционные тесты — 15 из 15; панели дашбордов — 42 из 42 (38 с данными, 4 пустых списка отклонений); суточный отчёт по данным стенда — 1 из 1. Профиль `nodered` в CI только проходит `docker compose config` |
