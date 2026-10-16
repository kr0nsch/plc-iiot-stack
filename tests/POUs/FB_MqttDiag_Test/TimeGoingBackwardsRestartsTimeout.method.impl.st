coUnit.TEST('TimeGoingBackwardsRestartsTimeout');

fbFake.xLinkUp := FALSE;
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#30M, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Connecting, Message := 'no false timeout');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#30M + LTIME#10S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Backoff, Message := 'timeout counted from the new time');

coUnit.TEST_FINISHED();
