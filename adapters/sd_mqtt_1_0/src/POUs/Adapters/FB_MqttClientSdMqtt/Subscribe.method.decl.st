// Подписка одним подписчиком библиотеки (адаптеру нужен один фильтр: <prefix>/+/+/cmd).
METHOD Subscribe : BOOL
VAR_INPUT
    sTopicFilter : STRING(GVL_Const.MQTT_TOPIC_LEN);
    eQos : E_MqttQos;
END_VAR
