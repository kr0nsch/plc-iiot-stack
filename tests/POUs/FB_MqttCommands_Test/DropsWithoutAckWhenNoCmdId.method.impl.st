coUnit.TEST('DropsWithoutAckWhenNoCmdId');

Setup(fbClient := fbFake, aRuleTable := aRules);
fbFake.Inject(sTopic := 'other/kns1/station/P101/cmd/Start',
    sPayload := '{"schema_version":"1.0","cmd_id":"c0000040","ts":1792137600000,"origin":"op1@test","command":"Start"}',
              xTruncated := FALSE, xRetained := FALSE);
fbFake.Inject(sTopic := 'vodokanal/kns1/station/P101/cmd/Start', sPayload := 'not json', xTruncated := FALSE,
    xRetained := FALSE);
fbFake.Inject(sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := '{"schema_version":"1.0","cmd_id":"short","ts":1792137600000,"origin":"op1@test","command":"Start"}',
              xTruncated := FALSE, xRetained := FALSE);
fbFake.Inject(sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := '{"schema_version":"1.0","command":"Start"}',
              xTruncated := FALSE, xRetained := FALSE);
fbFake.Inject(sTopic := 'vodokanal/kns1/station/P101/cmd/Start',
    sPayload := '{"schema_version":"1.0","cmd_id":"c0000041","ts":1792137600000,"origin":"op1@test","command":"Start"}',
              xTruncated := TRUE, xRetained := FALSE);
fbFake.Inject(sTopic := 'vodokanal/kns1/station/p101/cmd/Start',
    sPayload := '{"schema_version":"1.0","cmd_id":"c0000042","ts":1792137600000,"origin":"op1@test","command":"Start"}',
              xTruncated := FALSE, xRetained := FALSE);
fbCmd(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      uiMaxPerCycle := 10, aRules := aRules);
AssertEquals_UDINT(Expected := 6, Actual := fbCmd.udiDropped, Message := 'six messages dropped');
AssertEquals_UINT(Expected := 0, Actual := fbFake.uiPubCount, Message := 'no acks');

coUnit.TEST_FINISHED();
