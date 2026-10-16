coUnit.TEST('FailureAfterThresholdAndResetAfterStableLink');

fbFake.xConnectAccepts := FALSE;
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#1S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.eNe107 = E_IiotNe107.OutOfSpecification, Message := 'two failures: S');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#3S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertEquals_UINT(Expected := 3, Actual := fbDiag.uiConsecutiveFailures, Message := 'three in a row');
AssertTrue(Condition := fbDiag.eNe107 = E_IiotNe107.Failure, Message := 'three failures: F');
fbFake.xConnectAccepts := TRUE;
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#7S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Connected AND fbDiag.eNe107 = E_IiotNe107.Good,
           Message := 'connected: Good');
AssertEquals_UINT(Expected := 3, Actual := fbDiag.uiConsecutiveFailures, Message := 'kept until the link is stable');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#37S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertEquals_UINT(Expected := 0, Actual := fbDiag.uiConsecutiveFailures, Message := 'reset after tStable');
AssertEquals_TIME(Expected := T#1S, Actual := fbDiag.tBackoff, Message := 'pause back to minimum');

coUnit.TEST_FINISHED();
