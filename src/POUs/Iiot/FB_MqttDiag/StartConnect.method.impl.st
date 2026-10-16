stBrokerCfg.sWillTopic := StatusTopic();
IF BuildStatus(xOnline := FALSE, sReason := 'lwt') THEN
    stBrokerCfg.sWillPayload := fbJson.sJson;
ELSE
    stBrokerCfg.sWillPayload := '';
END_IF
stBrokerCfg.xWillRetain := TRUE;
EnterState(eNewState := E_MqttConnState.Connecting);
IF NOT itfClient.Connect(stCfg := stBrokerCfg) THEN
    ConnectFailed(diDefaultError := GVL_Const.MQTT_ERR_CONNECT_REJECTED);
END_IF
