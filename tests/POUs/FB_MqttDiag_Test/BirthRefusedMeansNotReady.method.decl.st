// Рождение не принято клиентом — связь есть, но публиковать нельзя; повтор.
METHOD PRIVATE BirthRefusedMeansNotReady
VAR_INST
    fbFake : FB_MqttClientFake;
    fbDiag : FB_MqttDiag;
    stCfg : ST_MqttBrokerCfg;
END_VAR
