# Раскладка исходников ST — формальный контракт

Документ фиксирует, как объекты проекта CODESYS лежат в `src/` и `tests/`. По этому контракту работают все инструменты:
`tools/assemble.py`, `tools/check/st_lint.py`, `tools/codesys/import_sources.py`, `tools/codesys/export_sources.py`.
Разбор раскладки реализован один раз — в `tools/codesys/stlayout.py` (общее подмножество Python 2.7 и 3.x),
его импортируют и скрипты CODESYS (IronPython 2.7), и инструменты на Python 3.

## Общие правила

- Кодировка UTF-8 без BOM, переводы строк LF, в конце файла — один перевод строки.
- Имя файла (до первой точки) совпадает с именем объекта CODESYS. Расхождение — ошибка `assemble` и `st_lint`.
- Отступы — 4 пробела, табы запрещены.
- Каталог внутри `src/DUTs`, `src/GVLs`, `src/Interfaces`, `src/POUs`, который **не** является объектом
  (нет файла `<Имя_каталога>.decl.st` / `<Имя_каталога>.itf.st`), — это папка проекта CODESYS.
  Папки вкладываются: `src/POUs/Devices/FB_Motor/FB_Motor.decl.st` → папка `Devices`, в ней `FB_Motor`.
  Для DUT и GVL папка — любой подкаталог: `src/DUTs/Motor/ST_MotorCmd.dut.st`.
- `tests/` устроен так же, как `src/`. При импорте с флагом тестов его объекты попадают в папку проекта `Tests`.

## Типы файлов

| Файл | Объект CODESYS | Содержимое файла |
|---|---|---|
| `DUTs/<Name>.dut.st` | DUT (структура, перечисление, объединение, псевдоним) | Полный текст редактора DUT: прагмы, `TYPE <Name> : ... END_TYPE` |
| `GVLs/<Name>.gvl.st` | Список глобальных переменных | Полный текст редактора GVL: прагмы, один или несколько блоков `VAR_GLOBAL ... END_VAR` |
| `GVLs/<Name>.pvl.st` | Persistent Variables | Текст объекта `VAR_GLOBAL PERSISTENT RETAIN ... END_VAR` (если API создания недоступно — ручной шаг) |
| `Interfaces/<I_Name>/<I_Name>.itf.st` | Интерфейс | Объявление: прагмы, `INTERFACE <I_Name> [EXTENDS ...]` — без `END_INTERFACE` |
| `Interfaces/<I_Name>/<M>.method.decl.st` | Метод интерфейса | `METHOD <M> [: <тип>]` и секции `VAR_INPUT/VAR_OUTPUT/VAR_IN_OUT` — без `END_METHOD` |
| `Interfaces/<I_Name>/<P>.prop.decl.st` | Свойство интерфейса | `PROPERTY <P> : <тип>` |
| `POUs/<Name>/<Name>.decl.st` | POU: `PROGRAM`, `FUNCTION_BLOCK`, `FUNCTION` | Текст редактора объявления: комментарий-заголовок, прагмы, строка `PROGRAM`/`FUNCTION_BLOCK ... [EXTENDS ...] [IMPLEMENTS ...]`/`FUNCTION ... : <тип>`, секции `VAR...END_VAR` — без `END_...` |
| `POUs/<Name>/<Name>.impl.st` | Тело POU | Только тело на ST. Пустое тело — файл с комментарием |
| `POUs/<Name>/<M>.method.decl.st` | Метод | `METHOD [PUBLIC\|PRIVATE\|PROTECTED\|INTERNAL] [ABSTRACT\|FINAL] <M> [: <тип>]` и секции переменных |
| `POUs/<Name>/<M>.method.impl.st` | Тело метода | Только тело |
| `POUs/<Name>/<P>.prop.decl.st` | Свойство | `PROPERTY [<доступ>] <P> : <тип>` |
| `POUs/<Name>/<P>.get.impl.st` | Аксессор Get | Тело Get |
| `POUs/<Name>/<P>.set.impl.st` | Аксессор Set | Тело Set |
| `.../<P>.get.decl.st`, `.../<P>.set.decl.st` | Объявление аксессора | Необязательно. Локальные переменные аксессора. Без файла — объявление по умолчанию `VAR` / `END_VAR` |

**Наличие аксессора.** Аксессор Get существует, если есть `<P>.get.impl.st` или `<P>.get.decl.st`; так же для Set.
У свойства без Set — только чтение. В интерфейсе аксессоры отмечают файлы `<P>.get.decl.st` / `<P>.set.decl.st`
(обычно пустые): у интерфейса нет реализаций.

**Порядок методов и свойств** в собранном тексте — по алфавиту (регистронезависимо), сначала методы, затем свойства.
Так экспорт и сборка детерминированы.

## Чего в раскладке нет (ручные шаги)

Визуализации, конфигурация задач, дерево устройств, Modbus/OPC UA конфигураторы, текстовые списки, графические
языки (FBD/LD/SFC/CFC), действия (`ACTION`) и переходы. Задачи и ссылки на библиотеки описываются в
`tools/codesys/config.json` и создаются скриптом; остальное — `docs/MANUAL_STEPS.md`.

## Собранный текст (`build/assembled/`)

`tools/assemble.py` склеивает объекты в стандартный ST (МЭК 61131-3, 3-я редакция) — по файлу на объект
верхнего уровня и общий `all.st`:

```
FUNCTION_BLOCK FB_Example IMPLEMENTS I_Resettable   // из FB_Example.decl.st
VAR_INPUT ... END_VAR
METHOD Reset : BOOL                                 // из Reset.method.decl.st
VAR_INPUT ... END_VAR
    ...                                             // из Reset.method.impl.st
END_METHOD
PROPERTY_GET Count : INT                            // свойство в синтаксисе RuSTy (в МЭК ред. 3 свойств нет)
    ...                                             // из Count.get.impl.st
END_PROPERTY
    ...                                             // тело из FB_Example.impl.st
END_FUNCTION_BLOCK
```

Варианты (`--flavor`):
- `iec` (по умолчанию) — как выше;
- `rusty` — плюс совместимые замены для компилятора RuSTy (см. `tools/check/rusty_exclude.txt` и README);
- `iec-checker` — понижение для разборщика iec_checker, который не понимает методы внутри `FUNCTION_BLOCK`
  и ряд расширений CODESYS. Используется только для статанализа; семантика может отличаться.
