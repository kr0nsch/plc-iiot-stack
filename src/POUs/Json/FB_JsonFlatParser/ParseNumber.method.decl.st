// Разобрать число по грамматике JSON -?(0|[1-9]d*)(.d+)?([eE][+-]?d+)? в lrTok. Нарушение грамматики,
// больше JSON_MANTISSA_DIGITS_MAX цифр, больше JSON_EXP_DIGITS_MAX цифр порядка, |x| > REAL_ABS_MAX —
// ошибка BadNumber.
METHOD PRIVATE ParseNumber : BOOL
VAR_IN_OUT CONSTANT
    // lint:allow STL007 параметр VAR_IN_OUT CONSTANT — ссылка только для чтения, а не константа
    sJson : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
VAR
    bCh : BYTE;
    xNegative : BOOL;
    xExpNegative : BOOL;
    lrMantissa : LREAL;
    uiDigits : UINT;       // цифр мантиссы
    iFracDigits : INT;     // цифр после точки
    uiExpDigits : UINT;
    iExp : INT;
    xHasExp : BOOL;
END_VAR
