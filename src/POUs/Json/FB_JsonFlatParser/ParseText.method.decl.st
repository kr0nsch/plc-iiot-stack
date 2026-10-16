// Разобрать строку в кавычках (позиция — на открывающей кавычке) в sTok. Длиннее uiMaxLen — ошибка
// eTooLong. Управляющие символы без экранирования, незакрытая строка — Syntax; \u вне ASCII — BadEscape.
METHOD PRIVATE ParseText : BOOL
VAR_IN_OUT CONSTANT
    // lint:allow STL007 параметр VAR_IN_OUT CONSTANT — ссылка только для чтения, а не константа
    sJson : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
VAR_INPUT
    uiMaxLen : UINT;
    eTooLong : E_JsonError;
END_VAR
VAR
    bCh : BYTE;
    uiOut : UINT;          // длина sTok
    uiHex : UINT;
    iDigit : INT;
    uiCode : UINT;         // код символа \uXXXX
END_VAR
