// Назначение: имя E_CmdResult устройства для поля cmd_result (коды 1..9); прочие — пусто.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Команды»
FUNCTION F_IiotCmdResultText : STRING(GVL_Const.IIOT_TEXT_LEN)
VAR_INPUT
    iResult : INT;    // TO_INT(stSts.stCommon.eCmdResult)
END_VAR
