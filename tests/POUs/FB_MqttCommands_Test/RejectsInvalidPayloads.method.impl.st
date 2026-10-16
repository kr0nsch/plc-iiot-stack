coUnit.TEST('RejectsInvalidPayloads');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000010","ts":1792137600000,',
                       '"origin":"op1@test","command":"Start","x":1}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.InvalidPayload, Message := 'extra field');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000011","ts":"1792137600000",',
                       '"origin":"op1@test","command":"Start"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.InvalidPayload, Message := 'ts as string');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000012","ts":1.7921376E12,',
                       '"origin":"op1@test","command":"Start"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.InvalidPayload, Message := 'ts not an integer literal');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := '{"schema_version":"1.0","cmd_id":"c0000013","ts":1000,"origin":"op1@test","command":"Start"}');
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.InvalidPayload, Message := 'ts out of range');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := '{"schema_version":"1.0","cmd_id":"c0000014","ts":1792137600000,"command":"Start"}');
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.InvalidPayload, Message := 'no origin');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := '{"schema_version":"1.0","cmd_id":"c0000015","ts":1792137600000,"origin":"op\n1","command":"Start"}');
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.InvalidPayload,
    Message := 'origin with a control character');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Explode',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000016","ts":1792137600000,',
                       '"origin":"op1@test","command":"Explode"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.InvalidPayload, Message := 'unknown command');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000017","ts":1792137600000,',
                       '"origin":"op1@test","command":"Start","value":1}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.InvalidPayload, Message := 'value on a pulse command');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000018","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.InvalidPayload, Message := 'SpeedSp without value');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/AckReq',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000019","ts":1792137600000,',
                       '"origin":"op1@test","command":"AckReq","value":1.5}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.InvalidPayload, Message := 'mask not an integer');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := CONCAT('{"schema_version":"1","cmd_id":"c0000020","ts":1792137600000,',
                       '"origin":"op1@test","command":"Start"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.InvalidPayload,
    Message := 'schema_version not MAJOR.MINOR');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"c0000021","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":"50"}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.InvalidPayload, Message := 'value as string');
AssertEquals_UDINT(Expected := 12, Actual := fbCmd.udiRejected, Message := 'every invalid payload is acked');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/cmd_ack/SpeedSp',
    sPart := '"reason":"invalid_payload"}'),
           Message := 'invalid_payload ack');

coUnit.TEST_FINISHED();
