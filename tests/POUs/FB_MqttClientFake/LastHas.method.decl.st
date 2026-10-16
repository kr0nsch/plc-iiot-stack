// Для тестов: последнее сообщение с топиком sTopic содержит sPart.
METHOD LastHas : BOOL
VAR_INPUT
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
    sPart : STRING(255);
END_VAR
VAR
    uiIdx : UINT;
END_VAR
