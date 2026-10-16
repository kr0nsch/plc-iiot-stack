coUnit.TEST('DisableWhileConnectedPublishesShutdown');

fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);
fbDiag(xEnable := FALSE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#1S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertEquals_STRING(
    Expected := '{"schema_version":"1.0","ts":1792137600250,"node":"PLC1","state":"offline","reason":"shutdown"}',
    Actual := fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/PLC1/status/connection'),
        Message := 'shutdown payload');
AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Closing, Message := 'closing');
AssertEquals_UINT(Expected := 0, Actual := fbFake.uiDisconnectCalls, Message := 'not yet disconnected');
fbDiag(xEnable := FALSE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#1S20MS, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertEquals_UINT(Expected := 1, Actual := fbFake.uiDisconnectCalls, Message := 'disconnected in the next call');
AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Disabled AND fbDiag.eNe107 = E_IiotNe107.CheckFunction,
           Message := 'disabled: C');

coUnit.TEST_FINISHED();
