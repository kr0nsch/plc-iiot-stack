// Назначение: строка из печатных символов ASCII (пробел..~) длиной 1..iMaxLen (поле origin).
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Команды»
FUNCTION F_IiotIsPrintable : BOOL
VAR_INPUT
    sText : STRING(GVL_Const.JSON_STR_LEN);
    iMaxLen : INT;
END_VAR
VAR
    iLen : INT;
    iIdx : INT;
    bCh : BYTE;
END_VAR
