// Первое принятое сообщение из очереди адаптера.
METHOD Receive : BOOL
VAR_IN_OUT
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
    sPayload : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
VAR_OUTPUT
    xTruncated : BOOL;
    xRetained : BOOL;      // версия 1.0.0.0 флаг retain принятого сообщения не отдаёт: всегда FALSE
END_VAR
VAR
    uiIdx : UINT;
END_VAR
