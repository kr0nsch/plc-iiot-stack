coUnit.TEST('DeviceSilenceIsTimeout');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000003","ts":1792137600000,',
                       '"origin":"op1@test","command":"Start"}'));
fbCmd.Arm(uiSeqBefore := 5);
fbFake.Inject(sTopic := 'vodokanal/kns1/station/P101/cmd/Ack',
    sPayload := '{"schema_version":"1.0","cmd_id":"c0000004","ts":1792137600000,"origin":"op1@test","command":"Ack"}',
              xTruncated := FALSE, xRetained := FALSE);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#2S999MS, uliNow_ms := 1792137600250, uiSeq := 5, iResult := 0,
    sTopic := '',
    sPayload := '');
AssertTrue(Condition := fbCmd.xPending, Message := 'still pending before 3 s');
AssertEquals_UINT(Expected := 1, Actual := fbFake.uiInCount, Message := 'next command waits in the queue');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#3S, uliNow_ms := 1792137600250, uiSeq := 5, iResult := 0,
    sTopic := '',
    sPayload := '');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/cmd_ack/Start',
    sPart := '"result":"rejected","reason":"timeout"}'),
           Message := 'timeout ack');
AssertTrue(Condition := fbCmd.xCmdValid AND fbCmd.stCmd.eCommand = E_IiotCommand.Ack,
           Message := 'next command processed after the timeout');

coUnit.TEST_FINISHED();
