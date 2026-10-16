coUnit.TEST('DeviceRejectedCarriesCmdResult');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000002","ts":1792137600000,',
                       '"origin":"op1@test","command":"Start"}'));
fbCmd.Arm(uiSeqBefore := 5);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 6, iResult := 2,
    sTopic := '',
    sPayload := '');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/cmd_ack/Start',
           sPart := '"result":"rejected","reason":"device_rejected","cmd_result":"RejectedMode"}'),
           Message := 'device_rejected with cmd_result');
AssertEquals_UDINT(Expected := 1, Actual := fbCmd.udiRejected, Message := 'rejected counter');

coUnit.TEST_FINISHED();
