// Для тестов: сколько сообщений с топиком sTopic.
METHOD CountTopic : UINT
VAR_INPUT
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
END_VAR
VAR
    uiIdx : UINT;
END_VAR
