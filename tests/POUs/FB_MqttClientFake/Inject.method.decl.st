// Для тестов: поставить входящее сообщение в очередь. FALSE — очередь полна.
METHOD Inject : BOOL
VAR_INPUT
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
    sPayload : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
    xTruncated : BOOL;
    xRetained : BOOL;
END_VAR
