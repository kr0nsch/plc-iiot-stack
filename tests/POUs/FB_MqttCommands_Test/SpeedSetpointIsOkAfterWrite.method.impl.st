coUnit.TEST('SpeedSetpointIsOkAfterWrite');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000005","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":45.5}'));
AssertTrue(Condition := fbCmd.xCmdValid, Message := 'speed passed the gateway');
AssertEquals_REAL(Expected := 45.5, Actual := fbCmd.stCmd.rValue, Delta := 0.0001, Message := 'speed value');
fbCmd.Arm(uiSeqBefore := 5);
AssertFalse(Condition := fbCmd.xPending, Message := 'no waiting for value commands');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/cmd_ack/SpeedSp',
    sPart := '"result":"accepted","reason":"ok"}'),
           Message := 'ok right after the write');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000006","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":0}'));
AssertTrue(Condition := fbCmd.xCmdValid, Message := 'lower bound 0 accepted');
fbCmd.Arm(uiSeqBefore := 5);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000007","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":100}'));
AssertTrue(Condition := fbCmd.xCmdValid, Message := 'upper bound 100 accepted');

coUnit.TEST_FINISHED();
