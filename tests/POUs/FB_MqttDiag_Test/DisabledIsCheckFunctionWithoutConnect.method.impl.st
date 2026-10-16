coUnit.TEST('DisabledIsCheckFunctionWithoutConnect');

fbDiag(xEnable := FALSE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Disabled, Message := 'state Disabled');
AssertTrue(Condition := fbDiag.eNe107 = E_IiotNe107.CheckFunction, Message := 'NE107 C');
AssertEquals_UINT(Expected := 0, Actual := fbFake.uiConnectCalls, Message := 'no connect while disabled');

coUnit.TEST_FINISHED();
