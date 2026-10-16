// Пауза между попытками: 1, 2, 4 с и дальше 4 с (tBackoffMax).
METHOD PRIVATE BackoffDoublesUpToMaximum
VAR_INST
    fbFake : FB_MqttClientFake;
    fbDiag : FB_MqttDiag;
    stCfg : ST_MqttBrokerCfg;
END_VAR
