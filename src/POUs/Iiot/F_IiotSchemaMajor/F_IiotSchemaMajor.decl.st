// Назначение: мажорная версия из schema_version вида MAJOR.MINOR (цифры без ведущих нулей);
//             не по формату — -1.
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Команды»
FUNCTION F_IiotSchemaMajor : INT
VAR_INPUT
    sVersion : STRING(GVL_Const.JSON_STR_LEN);
END_VAR
VAR
    iLen : INT;
    iIdx : INT;
    bCh : BYTE;
    iPart : INT;          // 0 — MAJOR, 1 — MINOR
    iDigits : INT;        // цифр в текущей части
    xLeadZero : BOOL;     // часть начинается с 0
    iMajor : INT;
END_VAR
