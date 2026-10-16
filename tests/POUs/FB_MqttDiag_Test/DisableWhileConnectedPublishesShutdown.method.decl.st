// Выключение при связи: offline/shutdown, затем разрыв в следующем вызове.
METHOD PRIVATE DisableWhileConnectedPublishesShutdown
VAR_INST
    fbFake : FB_MqttClientFake;
    fbDiag : FB_MqttDiag;
    stCfg : ST_MqttBrokerCfg;
END_VAR
