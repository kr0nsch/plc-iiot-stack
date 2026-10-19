// Назначение: разбор подмножества JSON для команд: один плоский объект, значения — строки (до
//             JSON_STR_LEN, escape-последовательности ASCII), числа по грамматике JSON (в диапазоне
//             REAL), true, false, null. Вложенные объекты и массивы, повторяющиеся ключи, лишние
//             символы после объекта — отказ с причиной eError и позицией uiErrorPos.
//             Порядок: Parse(sJson), затем GetString, GetNumber, FieldType по ключу.
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Команды»
FUNCTION_BLOCK FB_JsonFlatParser
VAR_OUTPUT
    uiCount : UINT;                       // полей в разобранном объекте
    eError : E_JsonError := E_JsonError.None;
    uiErrorPos : UINT;                    // позиция ошибки (байт от 0)
END_VAR
VAR
    aFields : ARRAY[1..GVL_Const.JSON_MAX_FIELDS] OF ST_JsonField;
    uiPos : UINT;                         // текущая позиция разбора
    uiLen : UINT;                         // длина входа
    sTok : STRING(GVL_Const.JSON_STR_LEN);   // последний разобранный токен-строка (ключ или значение)
    lrTok : LREAL;                        // последнее разобранное число
    xTokInteger : BOOL;                   // число записано без дробной части и порядка
END_VAR
