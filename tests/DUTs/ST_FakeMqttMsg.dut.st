// Назначение: сообщение, опубликованное через подменный клиент FB_MqttClientFake.
// Документ:   docs/TEST_REPORT.md
{attribute 'qualified_only'}
TYPE ST_FakeMqttMsg :
STRUCT
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
    sPayload : STRING(GVL_Const.MQTT_PAYLOAD_LEN);
    eQos : E_MqttQos;
    xRetain : BOOL;
END_STRUCT
END_TYPE
