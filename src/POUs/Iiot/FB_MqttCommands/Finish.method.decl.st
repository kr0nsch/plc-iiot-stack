// Ответ в <prefix>/<sTopicDevice>/cmd_ack/<sTopicCommand>: schema_version, cmd_id, ts, command, result, reason
// и cmd_result (device_rejected). Счётчики принятых и отклонённых команд.
METHOD PRIVATE Finish
VAR_INPUT
    eReason : E_IiotCmdReason;
    iCmdResult : INT;             // E_CmdResult устройства; 0 — нет
END_VAR
VAR
    sResultText : STRING(GVL_Const.IIOT_TEXT_LEN);
    sPath : STRING(GVL_Const.MQTT_TOPIC_LEN);
END_VAR
