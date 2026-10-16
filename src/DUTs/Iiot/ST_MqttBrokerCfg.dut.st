// Назначение: параметры подключения к брокеру MQTT (I_MqttClient.Connect).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_MqttBrokerCfg :
STRUCT
    sHost : STRING(GVL_Const.BROKER_HOST_LEN);            // имя или адрес брокера
    uiPort : UINT := GVL_Const.MQTT_PORT_DEFAULT;         // 1883; с TLS обычно 8883
    xTls : BOOL;                                           // TLS; проверка сертификата — забота адаптера
    sClientId : STRING(GVL_Const.BROKER_CLIENT_ID_LEN) := 'kns1-plc1';
    sUser : STRING(GVL_Const.BROKER_SECRET_LEN);
    {attribute 'symbol' := 'none'}
    sPassword : STRING(GVL_Const.BROKER_SECRET_LEN);      // задаётся при наладке; в git и в OPC UA не попадает
    tKeepAlive : TIME := GVL_Const.KEEPALIVE_DEFAULT;
    xCleanSession : BOOL := TRUE;
    sWillTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);        // LWT: заполняет FB_MqttDiag перед Connect
    sWillPayload : STRING(GVL_Const.BROKER_WILL_LEN);     // LWT: заполняет FB_MqttDiag
    xWillRetain : BOOL := TRUE;
END_STRUCT
END_TYPE
