coUnit.TEST('BirthRefusedMeansNotReady');

fbFake.xPublishAccepts := FALSE;
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.xConnected AND NOT fbDiag.xReady, Message := 'connected but not ready');
fbFake.xPublishAccepts := TRUE;
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#20MS, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.xReady, Message := 'ready after birth');

coUnit.TEST_FINISHED();
