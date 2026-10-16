coUnit.TEST('RejectsDuplicateIncludingRejectedIds');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SetOos',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"dup00001","ts":1792137600000,',
                       '"origin":"op1@test","command":"SetOos"}'));
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Ack',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"dup00001","ts":1792137600000,',
                       '"origin":"op1@test","command":"Ack"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.Duplicate, Message := 'id of a rejected command');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Ack',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"dup00002","ts":1792137600000,',
                       '"origin":"op1@test","command":"Ack"}'));
AssertTrue(Condition := fbCmd.xCmdValid, Message := 'new id accepted');

coUnit.TEST_FINISHED();
