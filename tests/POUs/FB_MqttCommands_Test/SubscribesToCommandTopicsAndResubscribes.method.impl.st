coUnit.TEST('SubscribesToCommandTopicsAndResubscribes');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := '',
    sPayload := '');
AssertEquals_STRING(Expected := 'vodokanal/kns1/station/+/cmd/+', Actual := fbFake.sLastFilter,
    Message := 'subscription filter');
AssertTrue(Condition := fbFake.eLastFilterQos = E_MqttQos.AtLeastOnce, Message := 'subscription QoS 1');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := '',
    sPayload := '');
AssertEquals_UINT(Expected := 1, Actual := fbFake.uiSubscribeCalls, Message := 'subscribe once while connected');
fbFake.xLinkUp := FALSE;
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := '',
    sPayload := '');
AssertFalse(Condition := fbCmd.xSubscribed, Message := 'subscription lost with the link');
fbFake.xLinkUp := TRUE;
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := '',
    sPayload := '');
AssertEquals_UINT(Expected := 2, Actual := fbFake.uiSubscribeCalls, Message := 'resubscribed after reconnect');

coUnit.TEST_FINISHED();
