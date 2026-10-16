coUnit.TEST('RejectsExpired');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Ack',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000030","ts":1792137569000,',
                       '"origin":"op1@test","command":"Ack"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.Expired, Message := '31 s old');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Ack',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000031","ts":1792137631500,',
                       '"origin":"op1@test","command":"Ack"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.Expired, Message := '31 s ahead');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 0, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Ack',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000032","ts":1792137600000,',
                       '"origin":"op1@test","command":"Ack"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.Expired, Message := 'no PLC clock');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Ack',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000033","ts":1792137571250,',
                       '"origin":"op1@test","command":"Ack"}'));
AssertTrue(Condition := fbCmd.xCmdValid, Message := '29 s old is accepted');

coUnit.TEST_FINISHED();
