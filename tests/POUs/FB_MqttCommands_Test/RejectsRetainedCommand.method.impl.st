coUnit.TEST('RejectsRetainedCommand');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := TRUE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000009","ts":1792137600000,',
                       '"origin":"op1@test","command":"Start"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.Retained, Message := 'retained');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/cmd_ack/Start',
    sPart := '"result":"rejected","reason":"retained"}'),
           Message := 'retained ack');

coUnit.TEST_FINISHED();
