// Назначение: уровень топика по шаблону: первая — буква (только заглавная при xUpperOnly), дальше
//             буквы, цифры и _ (буквы только заглавные при xUpperOnly), длина 1..iMaxLen. Устройство:
//             [A-Z][A-Z0-9_]{0,15}; команда: [A-Za-z][A-Za-z0-9_]{0,31}.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Топики»
FUNCTION F_IiotIsName : BOOL
VAR_INPUT
    sText : STRING(GVL_Const.IIOT_LEVEL_LEN);
    iMaxLen : INT;
    xUpperOnly : BOOL;
END_VAR
VAR
    iLen : INT;
    iIdx : INT;
    bCh : BYTE;
    xUpper : BOOL;
    xLower : BOOL;
    xDigit : BOOL;
END_VAR
