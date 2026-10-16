// Для тестов: последнее сообщение с топиком sTopic равно sExpected (до 255 символов).
METHOD LastIs : BOOL
VAR_INPUT
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
    sExpected : STRING(255);
END_VAR
VAR
    uiIdx : UINT;
END_VAR
