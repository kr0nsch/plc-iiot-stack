coUnit.TEST('RejectsUnsupportedVersionAndTopicMismatch');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := CONCAT('{"schema_version":"2.0","cmd_id":"c0000022","ts":1792137600000,',
                       '"origin":"op1@test","command":"Start"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.UnsupportedVersion, Message := '2.0');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Stop',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000023","ts":1792137600000,',
                       '"origin":"op1@test","command":"Start"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.TopicMismatch, Message := 'Stop vs Start');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/cmd_ack/Stop',
    sPart := '"command":"Stop","result":"rejected"'),
           Message := 'ack on the topic command level');

coUnit.TEST_FINISHED();
