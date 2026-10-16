// Подключение: завещание offline/lwt, рождение online/birth (QoS 1, retain), xReady.
METHOD PRIVATE ConnectSetsLwtAndPublishesBirth
VAR_INST
    fbFake : FB_MqttClientFake;
    fbDiag : FB_MqttDiag;
    stCfg : ST_MqttBrokerCfg;
END_VAR

VAR
    uiIdx : UINT;
END_VAR
