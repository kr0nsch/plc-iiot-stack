// Назначение: входящее сообщение в очереди подменного клиента FB_MqttClientFake.
// Документ:   docs/TEST_REPORT.md
{attribute 'qualified_only'}
TYPE ST_FakeMqttIn :
STRUCT
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
    sPayload : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
    xTruncated : BOOL;
    xRetained : BOOL;
END_STRUCT
END_TYPE
