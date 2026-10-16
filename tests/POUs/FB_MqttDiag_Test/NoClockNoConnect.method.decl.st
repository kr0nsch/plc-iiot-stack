// Часы ПЛК не установлены: подключения нет, код -5, статус C.
METHOD PRIVATE NoClockNoConnect
VAR_INST
    fbFake : FB_MqttClientFake;
    fbDiag : FB_MqttDiag;
    stCfg : ST_MqttBrokerCfg;
END_VAR
