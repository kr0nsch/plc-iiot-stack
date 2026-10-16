// Рост отказов публикаций за окно — M; нет роста — снова Good.
METHOD PRIVATE DegradedWhenPublishFailuresGrow
VAR_INST
    fbFake : FB_MqttClientFake;
    fbDiag : FB_MqttDiag;
    stCfg : ST_MqttBrokerCfg;
END_VAR
