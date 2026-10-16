// Выключено: Disabled, статус C, подключений нет.
METHOD PRIVATE DisabledIsCheckFunctionWithoutConnect
VAR_INST
    fbFake : FB_MqttClientFake;
    fbDiag : FB_MqttDiag;
    stCfg : ST_MqttBrokerCfg;
END_VAR
