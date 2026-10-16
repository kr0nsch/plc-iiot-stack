// Нет CONNACK за tConnectTimeout — неудача, код -2, разрыв, пауза, статус S.
METHOD PRIVATE ConnectTimeoutGoesToBackoff
VAR_INST
    fbFake : FB_MqttClientFake;
    fbDiag : FB_MqttDiag;
    stCfg : ST_MqttBrokerCfg;
END_VAR
