// Назначение: причина отказа разбора JSON (FB_JsonFlatParser).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_JsonError :
(
    None := 0,   // ошибок нет
    Empty := 1,   // пустой вход
    Syntax := 2,   // нарушен синтаксис JSON
    Nested := 3,   // вложенный объект или массив: не поддерживается
    Duplicate := 4,   // ключ повторяется
    TooManyFields := 5,   // полей больше JSON_MAX_FIELDS
    KeyTooLong := 6,   // ключ длиннее JSON_KEY_LEN
    ValueTooLong := 7,   // строка длиннее JSON_STR_LEN
    BadEscape := 8,   // неизвестная escape-последовательность или код вне ASCII
    BadNumber := 9,   // число не по грамматике JSON или вне диапазона REAL
    Trailing := 10   // лишние символы после объекта
) INT;
END_TYPE
