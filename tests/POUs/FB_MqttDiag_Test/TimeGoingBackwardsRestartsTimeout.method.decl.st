// Время пошло назад — отсчёт тайм-аута заново, без зависания.
METHOD PRIVATE TimeGoingBackwardsRestartsTimeout
VAR_INST
    fbFake : FB_MqttClientFake;
    fbDiag : FB_MqttDiag;
    stCfg : ST_MqttBrokerCfg;
END_VAR
