# Статический анализ

Находки `iec_checker` по `build/assembled/` (и `st_lint` по `src/`, `tests/`), которые не
исправлены в коде, — с обоснованием. Исправленные находки сюда не пишутся (кроме списка «исправлено по
итогам прогона»). Здесь же — итог проверки компиляции RuSTy.

## Как запускается

| Инструмент | Где | Вход | Отчёт |
|---|---|---|---|
| `tools/check/st_lint.py --strict` | локально и в CI | `src/`, `tests/` | вывод в консоль, код выхода ≠ 0 при нарушениях |
| `tools_project/iec_checker_gate.py` | локально и в CI (обязательно): бинарник iec_checker v0.4 из релизов github.com/jubnzv/iec-checker | `build/assembled/iec-checker/` (вариант сборки `iec-checker` + понижение обёртки) | `build/iec_checker.json`, `build/iec_checker.md`, `build/iec_checker_gate.json` |
| то же с `--docker` | CI, необязательное задание: образ `jubnzv1/iec-checker:nightly`, закреплённый по дайджесту в `ci.yml` | то же | то же, артефакт `iec-checker-nightly-reports` |
| `tools/check/run_rusty.py` | локально и в CI (необязательное задание): RuSTy `plc --check` | `build/assembled/rusty/` (вариант сборки `rusty`, `src/` и `tests/`) | `build/rusty.log`, `build/rusty.json` |

### Почему обёртка, а не `run_iec_checker.py`

iec_checker 0.4 не разбирает несколько конструкций CODESYS, без которых ПЛК-часть стека не
обходится: длину строки и границы массива из именованной константы (`STRING(GVL_Const.MQTT_TOPIC_LEN)`,
`ARRAY[1..GVL_IiotMap.POINT_COUNT]`), поле элемента массива `a[i].b`, `AND_THEN`, оператор `LTIME()`,
целый литерал больше 2^62. На каждой такой конструкции разборщик останавливается (ParserError), и файл
дальше не анализируется. Прямой запуск `run_iec_checker.py --tests` давал 41 ошибку разбора — без
анализа остались почти все POU `src/`. Шаблонные `tools/check/*.py` и `tools/st_flavors.py` в проекте
не правятся, поэтому `tools_project/iec_checker_gate.py`:

1. собирает вариант `iec-checker` тем же `tools/assemble.py`;
2. понижает собранный текст **только для анализа** и без смены номеров строк:
   - имена констант в `STRING[...]` и `ARRAY[...]` заменяет их значениями из исходников (213 замен);
   - возвращает `;` объявлениям `POINT_CFG`, `RULE_CFG`, `ALARM_CFG`: понижение шаблона убирает
     многострочное начальное значение, но оставляет `;` отдельной строкой (3);
   - `AND_THEN`/`OR_ELSE` → `AND`/`OR` (9): порядок вычисления для этих проверок не важен;
   - `a[i].b.c` → `a[i]` (521): iec_checker 0.4 не знает поля после индекса, а обращения к полям
     структур и так не считает использованием переменной;
3. классифицирует находки по `tools/check/iec_checker_allow.toml`, как `run_iec_checker.py`;
4. находку UnusedVariable, у которой в теле POU или его методе есть обращение к переменной, отмечает
   обоснованной с местом обращения (147 находок): iec_checker 0.4 не видит обращений из методов (сборка
   выносит их в функции), к полям и методам ФБ и структур (`fbParser.Parse(...)`, `stCmd.xAck`), через
   `ADR()` и `^`;
5. ParserError и UnknownError принимает только в местах из `tools_project/iec_checker_parser_gaps.toml`;
   устаревшая запись о пробеле и неиспользованное обоснование — ошибка.

Проверки обёртки — `tests_stack/test_iec_checker_gate.py` (понижение, проверка обращений, пробелы,
интеграционный прогон на исходниках репозитория); он же заменяет шаблонный
`test_integration_repository_sources` (в `pyproject.toml` отключён: тот запускает
`run_iec_checker.py` напрямую).

## Последний прогон

| Дата | Инструмент | Вход | Итог |
|---|---|---|---|
| 2026-10-16 | CODESYS 3.5.17.30, `cds.py build` / `cds.py test` | рабочее и тестовое приложения | 0 ошибок, 0 предупреждений |
| 2026-10-16 | `st_lint --strict` | `src/`, `tests/` (500 файлов) | 0 ошибок, 0 предупреждений |
| 2026-10-16 | `st_lint --strict --root adapters/sd_mqtt_1_0` | адаптер CODESYS-MQTT (20 файлов) | 0 ошибок, 0 предупреждений |
| 2026-10-16 | `iec_checker_gate.py --no-tests` (iec_checker 0.4, Windows) | 81 объект `src/` | пройдено: необоснованных 0; пробел разборщика 1 (`F_IiotNow`); обоснованных 1221: CP3 — 536, OutOfBounds — 350, L17 — 179, UnusedVariable — 98 (74 — с найденным обращением), CP9 — 53, L10 — 5; артефактов сборки 215 |
| 2026-10-16 | `iec_checker_gate.py` (iec_checker 0.4, Windows) | 94 объекта `src/` и `tests/` | пройдено: необоснованных 0; пробелов разборщика 2; обоснованных 1732: CP3 — 818, OutOfBounds — 350, L17 — 197, CP9 — 188, UnusedVariable — 173 (149 — с найденным обращением), L10 — 6; артефактов сборки 263 |
| 2026-10-16 | `run_rusty.py` (RuSTy 1.0.6, `plc --check`, Windows) | 95 файлов `build/assembled/rusty/` | 414 ошибок в 21 файле, 19 предупреждений — расширения CODESYS, которых нет в RuSTy (раздел «RuSTy») |
| — | iec_checker 0.4 через обёртку (CI, Linux) | 94 объекта `src/` и `tests/` | _перенести из отчёта CI_ |
| — | iec_checker `nightly` (CI, необязательно) | то же | _перенести из отчёта CI_ |

Исправлено по итогам прогона (для истории): неиспользуемые локальные переменные в четырёх тестах
(`DecodesEscapes`, `TracksIntegerLiterals`, `NonFiniteTransitionsAreChanges`,
`ZeroNegativeOrNanDeadbandMeansAnyChange`); неиспользуемая константа `GVL_Const.MS_PER_S`; типизированный
литерал в вызове `SHL(WORD#1, …)` (`F_IiotAlarmStateOf`) заменён константой; `LTIME()` вынесен из
`PRG_Iiot` в `F_IiotNow`, чтобы `PRG_Iiot` анализировался; методы `FB_IiotKnsMap.Fill*` получили проверку
границ массива (`LOWER_BOUND`/`UPPER_BOUND`).

## iec_checker: пробелы разборщика

| Файл | Конструкция | Почему не заменить |
|---|---|---|
| `src/POUs/Iiot/F_IiotNow/F_IiotNow.impl.st` | `LTIME()` | монотонное время без сторонних библиотек; оператор вызывается только здесь, остальной код получает время вызовом `F_IiotNow()` |
| `tests/POUs/FB_JsonBuilder_Test/IntExtremes.method.impl.st` | `LINT#9223372036854775807` | граница LINT в тесте сериализации; iec_checker 0.4 читает литерал в 63-битное целое OCaml (`Failure int_of_string`) |

Оба объекта проверяют компилятор CODESYS, тесты coUnit (`NowIsMonotonic`, `IntExtremes`) и `st_lint`.

## Находки

| Правило | Где | Находка | Решение / обоснование |
|---|---|---|---|
| PLCOPEN-CP3 | `src/`, `tests/` | «Variable … shall be initialized before being used» | Обосновано. Переменная без явного начального значения получает значение по умолчанию своего типа (МЭК 61131-3, как в CODESYS). Вариант сборки `iec-checker` убирает неконстантные начальные значения (`:= GVL_Const.ИМЯ`), отсюда часть находок; часть — на копиях переменных в методах, которые сборка понижает до функций |
| OutOfBounds | `FB_IiotKnsMap` (`FillPoints`, `FillAlarmWords`) | «index N is out of range [0 .. 0]» (350) | Артефакт понижения: параметр `ARRAY[*]` вариант сборки заменяет на `ARRAY[0..0]`. Индексы — константы генератора 1…`POINT_COUNT` и 1…`ALARM_WORDS_COUNT`; массив, который короче перечня или начинается не с 1, методы не заполняют (проверка `LOWER_BOUND`/`UPPER_BOUND`, тест `MapIgnoresTooSmallTable`) |
| PLCOPEN-L17 | `src/`, `tests/` | «Each IF instruction should have an ELSE clause» | Решение проекта: IF без ELSE там, где действия «иначе» нет — охранные проверки с `RETURN`, счётчики, однократные события. Правило PLCopen — рекомендация оформления; пустые ветки `ELSE` в 196 местах только добавили бы шум |
| PLCOPEN-CP9 | `FB_IiotKnsMap` | «Code is too complex (309 McCabe / 478 statements)» | Сгенерированный код: по строке на метрику, команду и устройство (121, 77, 29), без собственной логики — размер растёт с перечнем тегов |
| PLCOPEN-CP9 | `FB_JsonBuilder`, `FB_JsonFlatParser` | «too complex (22…131 McCabe)» | Посимвольная грамматика JSON (CASE по символу, числа, escape-последовательности); логика разделена на методы. iec_checker 0.4 считает сложность завышенно: по проверке в шаблоне plc-repo-template на синтетическом примере одна конструкция `IF … ELSE … END_IF` прибавляет 5 |
| PLCOPEN-CP9 | `FB_MqttCommands`, `FB_MqttDiag`, `FB_MqttAlarms`, `FB_MqttTelemetry`, функции `F_Iiot*` | «too complex (17…114 McCabe)» | Порядок проверок шлюза команд задан контрактом (data_schema.md, 5.1), диагностика — автомат состояний связи, тревоги — правила переходов; функции текстов — CASE по значениям перечислений схемы. Каждая проверка покрыта тестом coUnit |
| PLCOPEN-CP9 | `PRG_Iiot` | «68 McCabe / 97 statements» | Последовательная обвязка: инициализация таблиц, клиент, время, ФБ и теги; ветвления — включение частей настройками |
| PLCOPEN-CP9 | `tests/` | «too complex» | Наборы и тесты — последовательности вызовов и проверок; метрика для тестов не показательна |
| PLCOPEN-L10 | `FB_MqttCommands` (тело), `FB_JsonFlatParser` (`Parse`, `ParseText`, `SkipSpace`), `F_TestContains` | «Usage of CONTINUE and EXIT instruction should be avoided» | `EXIT` завершает ограниченный цикл, когда результат известен: очередь приёма пуста или команда ждёт исполнения; конец лексемы или ошибка разбора; найдено совпадение. Флаг в условии цикла читался бы хуже |
| UnusedVariable | 147 мест в `src/` и `tests/` | «Found unused local variable» | Ложное срабатывание, проверено обёрткой: для каждой находки в теле POU или методе найдено обращение (место — в отчёте `build/iec_checker.md`) |
| UnusedVariable | `FB_MqttClientNone` (параметры методов) | то же (9) | Нулевой объект `I_MqttClient`: сигнатуры заданы интерфейсом, параметры намеренно не используются |
| UnusedVariable | `src/POUs/KnsShim/*` (входы ФБ-заглушек) | то же (15) | Заглушки флагмана без логики: значения пишут тесты, читает `PRG_Iiot` снаружи (`GVL_Devices.fb<TAG>.<имя>`) |

## RuSTy (`plc --check`)

Необязательная проверка: RuSTy 1.0.6 проверяет синтаксис и типы варианта сборки `rusty`; компоновки нет,
объявления coUnit и блоков Standard — из прокладок шаблона `tools/check/rusty_shims/`. Последний
прогон — 414 ошибок в 21 файле из 95; все — конструкции CODESYS, которых нет в RuSTy или в прокладках, а
не ошибки кода (компилятор CODESYS — 0 ошибок, 0 предупреждений):

| Ошибки | Число | Причина |
|---|---|---|
| E034, E036 | 13 + 87 | `VAR_IN_OUT CONSTANT` RuSTy не поддерживает (E034) и затем считает передачу аргумента записью в константу (E036) |
| E037 | 14 | передача параметра `ARRAY[*]` в другой параметр `ARRAY[*]` |
| E059, E073 | 21 + 2 | обращение к символу строки `s[i]` (расширение CODESYS) |
| E032, E089, E048 | 84 + 84 + 84 | вызовы метода-помощника `Run` наборов `FB_MqttCommands_Test` и `FB_MqttTelemetry_Test` (параметры — `VAR_IN_OUT` экземпляров ФБ и `ARRAY[*]`, входы с начальными значениями): RuSTy считает, что метод без параметров |
| E048 | 21 | `BOOL_TO_LREAL`, `BYTE_TO_LREAL` нет в прокладках шаблона |
| E048 | 4 | `SysTimeRtcHighResGet` (библиотека SysTimeRtc) нет в прокладках шаблона |
| E067 (предупреждения) | 19 | неявное сужение типов: `LEN()` (в RuSTy — DINT) в INT/UINT, `MAX()`, `SIZEOF()` в проверках тестов |

Исключать эти файлы через `tools/check/rusty_exclude.txt` бессмысленно: на них ссылаются остальные
объекты, и исключение одного файла даёт ошибки «не найдено» в зависимых. Задание RuSTy в CI остаётся
необязательным; прокладки шаблона (`BOOL_TO_LREAL`, SysTimeRtc) — предложение в репозиторий шаблона.
