// Потеря связи: разрыв, код -4, пауза 1 с, переподключение и новое рождение.
METHOD PRIVATE ConnectionLossCountsAndReconnects
VAR_INST
    fbFake : FB_MqttClientFake;
    fbDiag : FB_MqttDiag;
    stCfg : ST_MqttBrokerCfg;
END_VAR
