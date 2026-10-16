// Connect() отклонён: код ошибки клиента, без него — -3.
METHOD PRIVATE RejectedConnectUsesClientErrorCode
VAR_INST
    fbFake : FB_MqttClientFake;
    fbDiag : FB_MqttDiag;
    stCfg : ST_MqttBrokerCfg;
END_VAR
