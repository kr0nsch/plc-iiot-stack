// Назначение: текст причины для поля reason ответа на команду.
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Команды»
FUNCTION F_IiotCmdReasonText : STRING(GVL_Const.IIOT_TEXT_LEN)
VAR_INPUT
    eReason : E_IiotCmdReason;
END_VAR
