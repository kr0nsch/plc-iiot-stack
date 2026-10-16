coUnit.TEST('RateLimitTenPerTenSeconds');

Setup(fbClient := fbFake, aRuleTable := aRules);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#0MS, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"rate0000","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":50}'));
fbCmd.Arm(uiSeqBefore := 0);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#100MS, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"rate0001","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":50}'));
fbCmd.Arm(uiSeqBefore := 0);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#200MS, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"rate0002","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":50}'));
fbCmd.Arm(uiSeqBefore := 0);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#300MS, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"rate0003","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":50}'));
fbCmd.Arm(uiSeqBefore := 0);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#400MS, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"rate0004","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":50}'));
fbCmd.Arm(uiSeqBefore := 0);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#500MS, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"rate0005","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":50}'));
fbCmd.Arm(uiSeqBefore := 0);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#600MS, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"rate0006","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":50}'));
fbCmd.Arm(uiSeqBefore := 0);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#700MS, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"rate0007","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":50}'));
fbCmd.Arm(uiSeqBefore := 0);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#800MS, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"rate0008","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":50}'));
fbCmd.Arm(uiSeqBefore := 0);
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#900MS, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"rate0009","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":50}'));
fbCmd.Arm(uiSeqBefore := 0);
AssertEquals_UDINT(Expected := 10, Actual := fbCmd.udiAccepted, Message := 'ten commands within the window');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#1S, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"rate0010","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":50}'));
AssertTrue(Condition := fbCmd.eLastReason = E_IiotCmdReason.RateLimited, Message := 'eleventh within 10 s');
Run(fbClient := fbFake, fbCommands := fbCmd, aRuleTable := aRules, xRetainedIn := FALSE,
    ltAt := LTIME#1H + LTIME#10S100MS, uliNow_ms := 1792137600250, uiSeq := 0, iResult := 0,
    sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp',
    sPayload := CONCAT('{"schema_version":"1.0","cmd_id":"rate0011","ts":1792137600000,',
                       '"origin":"op1@test","command":"SpeedSp","value":50}'));
AssertTrue(Condition := fbCmd.xCmdValid, Message := 'accepted after the window');

coUnit.TEST_FINISHED();
