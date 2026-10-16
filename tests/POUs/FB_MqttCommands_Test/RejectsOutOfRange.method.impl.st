coUnit.TEST('RejectsOutOfRange');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000028","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":100.5}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.OutOfRange, Message := '100.5');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000029","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":-0.1}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.OutOfRange, Message := '-0.1');

coUnit.TEST_FINISHED();
