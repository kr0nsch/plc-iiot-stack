coUnit.TEST('BackoffDoublesUpToMaximum');

fbFake.xConnectAccepts := FALSE;
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station', tBackoffMax := T#4S,
       stBroker := stCfg);
AssertEquals_UINT(Expected := 1, Actual := fbFake.uiConnectCalls, Message := 'attempts at LTIME#1H');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#999MS, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station', tBackoffMax := T#4S,
       stBroker := stCfg);
AssertEquals_UINT(Expected := 1, Actual := fbFake.uiConnectCalls, Message := 'attempts at LTIME#1H + LTIME#999MS');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#1S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station', tBackoffMax := T#4S,
       stBroker := stCfg);
AssertEquals_UINT(Expected := 2, Actual := fbFake.uiConnectCalls, Message := 'attempts at LTIME#1H + LTIME#1S');
AssertEquals_TIME(Expected := T#2S, Actual := fbDiag.tBackoff, Message := 'next pause T#2S');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#2S999MS, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station', tBackoffMax := T#4S,
       stBroker := stCfg);
AssertEquals_UINT(Expected := 2, Actual := fbFake.uiConnectCalls, Message := 'attempts at LTIME#1H + LTIME#2S999MS');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#3S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station', tBackoffMax := T#4S,
       stBroker := stCfg);
AssertEquals_UINT(Expected := 3, Actual := fbFake.uiConnectCalls, Message := 'attempts at LTIME#1H + LTIME#3S');
AssertEquals_TIME(Expected := T#4S, Actual := fbDiag.tBackoff, Message := 'next pause T#4S');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#7S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station', tBackoffMax := T#4S,
       stBroker := stCfg);
AssertEquals_UINT(Expected := 4, Actual := fbFake.uiConnectCalls, Message := 'attempts at LTIME#1H + LTIME#7S');
AssertEquals_TIME(Expected := T#4S, Actual := fbDiag.tBackoff, Message := 'next pause T#4S');
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#11S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station', tBackoffMax := T#4S,
       stBroker := stCfg);
AssertEquals_UINT(Expected := 5, Actual := fbFake.uiConnectCalls, Message := 'attempts at LTIME#1H + LTIME#11S');

coUnit.TEST_FINISHED();
