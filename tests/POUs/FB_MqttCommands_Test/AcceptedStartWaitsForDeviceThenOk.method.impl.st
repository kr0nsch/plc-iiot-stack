coUnit.TEST('AcceptedStartWaitsForDeviceThenOk');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000001","ts":1792137600000,',
                       '"origin":"op1@test","command":"Start"}'));
AssertTrue(Condition := fbCmd.xCmdValid, Message := 'command passed the gateway');
AssertTrue(Condition := fbCmd.stCmd.eCommand = E_IiotCommand.Start, Message := 'command Start');
AssertEquals_DINT(Expected := 1, Actual := fbCmd.stCmd.diRule, Message := 'rule index');
AssertEquals_STRING(Expected := 'P101', Actual := fbCmd.stCmd.sDevice, Message := 'device');
AssertEquals_STRING(Expected := 'c0000001', Actual := fbCmd.stCmd.sCmdId, Message := 'cmd_id');
fbCmd.Arm(uiSeqBefore := 5);
AssertTrue(Condition := fbCmd.xPending, Message := 'waiting for the device');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 5, iResult := 1,
    sTopic := '',
    sPayload := '');
AssertEquals_UINT(Expected := 0, Actual := fbFake.CountTopic(sTopic := 'vodokanal/kns1/station/P101/cmd_ack/Start'),
    Message := 'no ack yet');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 6, iResult := 1,
    sTopic := '',
    sPayload := '');
AssertEquals_STRING(Expected := CONCAT('{"schema_version":"1.0","cmd_id":"c0000001","ts":1792137600250,',
                                       '"command":"Start","result":"accepted","reason":"ok"}'),
                    Actual := fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/P101/cmd_ack/Start'),
                        Message := 'ack JSON');
AssertTrue(Condition := NOT fbFake.aPub[fbFake.uiPubCount].xRetain, Message := 'ack is not retained');
AssertEquals_UDINT(Expected := 1, Actual := fbCmd.udiAccepted, Message := 'accepted counter');
AssertFalse(Condition := fbCmd.xPending, Message := 'not pending');

coUnit.TEST_FINISHED();
