// Три неудачи подряд — F; после tStable связи счётчик и пауза сбрасываются.
METHOD PRIVATE FailureAfterThresholdAndResetAfterStableLink
VAR_INST
    fbFake : FB_MqttClientFake;
    fbDiag : FB_MqttDiag;
    stCfg : ST_MqttBrokerCfg;
END_VAR
