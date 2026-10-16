// Назначение: настройки ПЛК-части IIoT-стека (GVL_Iiot.stIiotCfg); топики — schema/topics.json.
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_IiotCfg :
STRUCT
    xEnable : BOOL;                                    // обмен MQTT включён (по умолчанию выключен до наладки)
    xCommandsEnable : BOOL;                            // приём команд MQTT (по умолчанию выключен)
    sSite : STRING(GVL_Const.IIOT_LEVEL_LEN) := 'vodokanal';
    sArea : STRING(GVL_Const.IIOT_LEVEL_LEN) := 'kns1';
    sUnit : STRING(GVL_Const.IIOT_LEVEL_LEN) := 'station';
    sNode : STRING(GVL_Const.IIOT_DEVICE_LEN) := 'PLC1';  // узел ПЛК: status/connection и метрики PLC1
    sSwVersion : STRING(GVL_Const.IIOT_TEXT_LEN) := '0.1.0';
    tTelemetryPeriod : TIME := GVL_Const.TELEMETRY_PERIOD_DEFAULT;
    stBroker : ST_MqttBrokerCfg;
END_STRUCT
END_TYPE
