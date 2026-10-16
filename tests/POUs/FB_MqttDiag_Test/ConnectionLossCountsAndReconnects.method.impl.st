coUnit.TEST('ConnectionLossCountsAndReconnects');

fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);
fbFake.xLinkUp := FALSE;
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#40S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Backoff AND NOT fbDiag.xReady, Message := 'backoff after loss');
AssertEquals_UDINT(Expected := 1, Actual := fbDiag.udiDisconnects, Message := 'disconnect counter');
AssertEquals_DINT(Expected := GVL_Const.MQTT_ERR_CONNECTION_LOST, Actual := fbDiag.diLastError, Message := 'loss code');
AssertTrue(Condition := fbDiag.eNe107 = E_IiotNe107.OutOfSpecification, Message := 'lost link: S');
fbFake.xLinkUp := TRUE;
fbFake.ClearPublished();
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#40S + LTIME#999MS, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Backoff, Message := 'waits the minimum pause');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#41S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Connected AND fbDiag.xReady, Message := 'reconnected');
AssertEquals_UDINT(Expected := 2, Actual := fbDiag.udiConnects, Message := 'second connect');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/PLC1/status/connection',
    sPart := '"reason":"birth"'), Message := 'birth again');

coUnit.TEST_FINISHED();
