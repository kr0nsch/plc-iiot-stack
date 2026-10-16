// Подписаться на фильтр топиков (допустимы + и #). TRUE — запрос подписки принят.
METHOD Subscribe : BOOL
VAR_INPUT
    sTopicFilter : STRING(GVL_Const.MQTT_TOPIC_LEN);
    eQos : E_MqttQos;
END_VAR
