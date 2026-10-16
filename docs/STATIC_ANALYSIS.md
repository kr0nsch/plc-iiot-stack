# Статический анализ

Находки `iec_checker` по `build/assembled/` (и `st_lint` по `src/`, `tests/`), которые не
исправлены в коде, — с обоснованием. Исправленные находки сюда не пишутся. Здесь же — итог
проверки компиляции RuSTy.

## Как запускается

| Инструмент | Где | Вход | Отчёт |
|---|---|---|---|
| `tools/check/st_lint.py --strict` | локально и в CI | `src/`, `tests/` | вывод в консоль, код выхода ≠ 0 при нарушениях |
| `tools/check/run_iec_checker.py --tests` | локально и в CI (обязательно): бинарник iec_checker v0.4 из релизов github.com/jubnzv/iec-checker | `build/assembled/iec-checker/` (вариант сборки `iec-checker`) | `build/iec_checker.json`, `build/iec_checker.md` |
| то же с `--docker` | CI, необязательное задание: образ `jubnzv1/iec-checker:nightly`, закреплённый по дайджесту в `ci.yml` | то же | то же, артефакт `iec-checker-nightly-reports` |
| `tools/check/run_rusty.py` | локально и в CI (необязательное задание): RuSTy `plc --check` | `build/assembled/rusty/` (вариант сборки `rusty`, `src/` и `tests/`) | `build/rusty.log`, `build/rusty.json` |

Обоснования в `tools/check/iec_checker_allow.toml` подобраны под находки v0.4 — той же версии, что в
обязательном шаге CI. Образ `nightly` разбирает больше конструкций и может находить иначе: если
находка есть только в одной версии — укажите это в столбце «решение». Интеграционный тест
`tools/tests/test_run_iec_checker.py::test_integration_repository_sources` проверяет, что каждое
обоснование используется: после правок примера уберите устаревшие записи.

## Последний прогон

| Дата | Инструмент | Вход | Итог |
|---|---|---|---|
| 2026-10-16 | `st_lint --strict` | `src/`, `tests/` (60 файлов) | 0 ошибок, 0 предупреждений |
| 2026-10-16 | `run_iec_checker.py` (iec_checker 0.4, Windows, локально) | 8 объектов `src/` | ошибок разбора нет; необоснованных 0; обоснованных 32: CP3 — 24, L17 — 4, CP9 — 2, UnusedVariable — 2; артефактов сборки 10 (CP3) |
| 2026-10-16 | `run_iec_checker.py --tests` (iec_checker 0.4, Windows, локально) | 11 объектов `src/` и `tests/` | ошибок разбора нет; необоснованных 0; обоснованных 100: CP3 — 49, UnusedVariable — 30, CP9 — 17, L17 — 4; артефактов сборки 10 (CP3) |
| 2026-10-16 | `run_rusty.py` (RuSTy 1.0.6, `plc --check`, Windows, локально) | 11 файлов `build/assembled/rusty/` (`src/` и `tests/` с прокладками coUnit и Standard) | 0 ошибок, 0 предупреждений; исключений в `rusty_exclude.txt` нет |
| — | iec_checker 0.4 (CI, Linux) | 11 объектов `src/` и `tests/` | _перенести из отчёта CI_ |
| — | iec_checker `nightly` (CI, необязательно) | то же | _перенести из отчёта CI_ |

## Находки

| Правило | Файл | Находка | Решение / обоснование |
|---|---|---|---|
| PLCOPEN-CP3 | все POU `src/` (34) | «Variable … shall be initialized before being used» для входов, выходов и локальных переменных без явного начального значения | Обосновано. В CODESYS, как и по МЭК 61131-3, переменная без явного начального значения получает значение по умолчанию своего типа (0, `FALSE`; у `E_DeviceMode` это `Auto = 0`). Явные значения стоят там, где умолчание не подходит: режим `OutOfService`, уставка и гистерезис из `GVL_Const`. Вариант сборки `iec-checker` убирает неконстантные начальные значения, поэтому находка есть и для них. Часть находок — на копиях переменных в методах, которые сборка понижает до функций (`Acknowledge`, `Reset`, `Count`) |
| PLCOPEN-CP9 | `FB_Example` (тело) | «Code is too complex (28 McCabe complexity)», «(26 statements)» | Обосновано. Пороги iec_checker 0.4 — сложность > 15 и > 25 операторов, а сложность он считает завышенно: проверено на синтетическом примере, одна конструкция `IF … ELSE … END_IF` прибавляет 5. Классическая цикломатическая сложность тела — 8 (7 точек ветвления: 3 в `CASE`, 3 в `IF … ELSIF`, 1 в счётчике). Делить 40 строк линейной логики на методы ради метрики — хуже для чтения |
| PLCOPEN-L17 | `FB_Example`: `IF xFault …` в режиме `Auto`, `IF` счётчика включений | «Each IF instruction should have an ELSE clause» | Обосновано: действия «иначе» нет. В зоне гистерезиса выход сохраняет состояние, без фронта счётчик не меняется. Пустая ветка `ELSE` или присваивание переменной самой себе только добавили бы шум |
| PLCOPEN-L17 | `PRG_Main`: обработка `stCmd.xAck`, `stCmd.xReset` | то же | Обосновано: однократная команда не пришла — делать нечего |
| UnusedVariable | `PRG_Main`: `stCmd`, `stSts` | «Found unused local variable» | Ложное срабатывание: переменные используются через поля (`stCmd.xAck`, `stSts.xOut := …`), iec_checker 0.4 обращения к полям структуры не учитывает. Перепроверить на образе `nightly` |

Исправлено по итогам прогона (для истории): защёлка отказа в `FB_Example` и квитирование в
`Acknowledge` записаны логическими выражениями вместо `IF` без `ELSE`.

### Если анализируются и тесты (`assemble --tests`)

| Правило | Файл | Находка | Решение / обоснование |
|---|---|---|---|
| UnusedVariable | `FB_F_Clamp_Test`: `R_LOW`, `R_HIGH`, `R_INSIDE`, `R_BELOW`, `R_ABOVE`, `R_DELTA`; `FB_Example_Test`: `R_SP_PCT`, `R_HYST_PCT`, … `UDI_TWO_SWITCH_ONS` (10) | «Found unused local variable» | Артефакт понижения: константы набора (`VAR CONSTANT`) используются в методах-тестах, которые сборка выносит в отдельные функции |
| UnusedVariable | `FB_Example_Test`: `fbDut` в 10 методах | то же | Ложное срабатывание, как для `stCmd`/`stSts` в `PRG_Main`: экземпляр используется вызовом `fbDut(...)`, чтением выходов и вызовом методов, iec_checker 0.4 это использованием не считает (в методе, где `fbDut` присваивается интерфейсу, находки нет) |
| UnusedVariable | `PRG_Tests`: `fbF_ClampTest`, `fbExampleTest` | то же | Ложное срабатывание: экземпляры используются вызовом `AreAllTestsFinished()` и регистрируются в coUnit самим объявлением |
| PLCOPEN-CP9 | `FB_F_Clamp_Test` (1), `FB_Example_Test` (14) | «Code is too complex (16…40 McCabe complexity)», «(33…48 statements)» | Обосновано: в наборах и методах-тестах нет ветвлений (классическая сложность — 1), это последовательности вызовов и проверок; завышенный подсчёт iec_checker. Для тестов метрика не показательна |
| PLCOPEN-CP3 | `FB_F_Clamp_Test`, `FB_Example_Test`, `PRG_Tests` (25) | как выше | Обосновано, как для `src/`: результаты и экземпляры получают значения до чтения |

## RuSTy (`plc --check`)

Компилятор RuSTy 1.0.6 проверяет синтаксис и типы варианта сборки `rusty` (`src/` и `tests/`); компоновки
нет. Пространства имён `coUnit.`/`CfUnit.` убираются, объявления coUnit и блоков CODESYS Standard берутся
из прокладок `tools/check/rusty_shims/` (сигнатуры — по исследованию API, с CODESYS не сверялись).
Последний прогон — в таблице выше: 0 ошибок, 0 предупреждений, исключений нет. Найденные RuSTy ошибки
исправляются в коде; файл, который RuSTy не может разобрать из-за расширения CODESYS, заносится в
`tools/check/rusty_exclude.txt` с причиной.

## Ограничения разборщика

Конструкции CODESYS, которые iec_checker 0.4 не разбирает, — и что с ними делает вариант сборки
`iec-checker` (подробно — [LAYOUT.md](LAYOUT.md#собранный-текст-buildassembled) и `tools/README.md`):

| Конструкция | Где в примере | Как обходится |
|---|---|---|
| метки `CASE` вида `E_DeviceMode.Auto` | `FB_Example` | сборка заменяет метки целыми значениями перечисления |
| неконстантные начальные значения (`:= E_DeviceMode.OutOfService`, `:= GVL_Const.ИМЯ`) | `FB_Example`, `ST_ExampleCmd` | сборка убирает начальное значение (отсюда часть находок CP3) |
| `VAR_GLOBAL` вне `CONFIGURATION`, прагмы `{attribute …}` | `GVL_Const`, `E_DeviceMode` | сборка понижает |
| методы и свойства внутри `FUNCTION_BLOCK`, `IMPLEMENTS`, `EXTENDS` | `FB_Example`, `FB_F_Clamp_Test`, `FB_Example_Test` | сборка выносит методы в функции `<ФБ>__<метод>` — анализ методов приблизительный |
