// Реализация I_MqttClient без транспорта.
METHOD Receive : BOOL
VAR_IN_OUT
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
    sPayload : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
VAR_OUTPUT
    xTruncated : BOOL;
    xRetained : BOOL;
END_VAR
