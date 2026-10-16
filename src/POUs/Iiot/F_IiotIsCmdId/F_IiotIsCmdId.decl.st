// Назначение: cmd_id по схеме: [A-Za-z0-9_-]{8,36}.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Команды»
FUNCTION F_IiotIsCmdId : BOOL
VAR_INPUT
    sText : STRING(GVL_Const.JSON_STR_LEN);
END_VAR
VAR
    iLen : INT;
    iIdx : INT;
    bCh : BYTE;
END_VAR
