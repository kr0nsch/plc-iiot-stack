// Для тестов: начало (255 символов) последнего сообщения с топиком sTopic — для текста отказа.
METHOD LastPayload : STRING(255)
VAR_INPUT
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
END_VAR
VAR
    uiIdx : UINT;
END_VAR
