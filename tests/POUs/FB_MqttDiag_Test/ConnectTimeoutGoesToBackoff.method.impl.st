coUnit.TEST('ConnectTimeoutGoesToBackoff');

fbFake.xLinkUp := FALSE;
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Connecting, Message := 'connecting');
AssertTrue(Condition := fbDiag.eNe107 = E_IiotNe107.CheckFunction, Message := 'first attempt: C');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#9S999MS, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Connecting, Message := 'still connecting before timeout');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#10S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Backoff, Message := 'backoff after timeout');
AssertEquals_DINT(Expected := GVL_Const.MQTT_ERR_CONNECT_TIMEOUT, Actual := fbDiag.diLastError,
    Message := 'timeout code');
AssertEquals_UDINT(Expected := 1, Actual := fbDiag.udiConnectFailures, Message := 'failure counter');
AssertEquals_UINT(Expected := 1, Actual := fbFake.uiDisconnectCalls, Message := 'client released');
AssertTrue(Condition := fbDiag.eNe107 = E_IiotNe107.OutOfSpecification, Message := 'NE107 S');

coUnit.TEST_FINISHED();
