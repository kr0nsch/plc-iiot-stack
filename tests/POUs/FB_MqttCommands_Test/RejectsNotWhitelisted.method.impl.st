coUnit.TEST('RejectsNotWhitelisted');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SetOos',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000024","ts":1792137600000,',
                       '"origin":"op1@test","command":"SetOos"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.NotWhitelisted, Message := 'SetOos');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/LT101/cmd/Start',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000025","ts":1792137600000,',
                       '"origin":"op1@test","command":"Start"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.NotWhitelisted, Message := 'Start for LT101');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/X999/cmd/Ack',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000026","ts":1792137600000,',
                       '"origin":"op1@test","command":"Ack"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.NotWhitelisted, Message := 'unknown device');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/LT101/cmd/Ack',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000027","ts":1792137600000,',
                       '"origin":"op1@test","command":"Ack"}'));
AssertTrue(Condition := fbCmd.xCmdValid AND fbCmd.stCmd.diRule = 4, Message := 'LT101 Ack is whitelisted');

coUnit.TEST_FINISHED();
