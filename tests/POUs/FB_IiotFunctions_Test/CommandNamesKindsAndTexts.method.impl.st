coUnit.TEST('CommandNamesKindsAndTexts');

AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'SetAuto') = E_IiotCommand.SetAuto, Message := 'SetAuto');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'SetManual') = E_IiotCommand.SetManual, Message := 'SetManual');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'SetOos') = E_IiotCommand.SetOos, Message := 'SetOos');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'Start') = E_IiotCommand.Start, Message := 'Start');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'Stop') = E_IiotCommand.Stop, Message := 'Stop');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'SpeedSp') = E_IiotCommand.SpeedSp, Message := 'SpeedSp');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'ResetMaint') = E_IiotCommand.ResetMaint,
           Message := 'ResetMaint');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'SubstValue') = E_IiotCommand.SubstValue,
           Message := 'SubstValue');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'Ack') = E_IiotCommand.Ack, Message := 'Ack');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'Reset') = E_IiotCommand.Reset, Message := 'Reset');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'AckReq') = E_IiotCommand.AckReq, Message := 'AckReq');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'ShelveReq') = E_IiotCommand.ShelveReq, Message := 'ShelveReq');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'UnshelveReq') = E_IiotCommand.UnshelveReq,
           Message := 'UnshelveReq');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'SetStepped') = E_IiotCommand.SetStepped,
           Message := 'SetStepped');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'SetLevelPid') = E_IiotCommand.SetLevelPid,
           Message := 'SetLevelPid');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'AckAll') = E_IiotCommand.AckAll, Message := 'AckAll');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'ResetAll') = E_IiotCommand.ResetAll, Message := 'ResetAll');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'Silence') = E_IiotCommand.Silence, Message := 'Silence');
AssertTrue(Condition := F_IiotCmdKind(eCommand := E_IiotCommand.AckAll) = E_IiotCmdKind.Pulse,
           Message := 'station command is a pulse');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'start') = E_IiotCommand.None, Message := 'case sensitive');
AssertTrue(Condition := F_IiotCmdFromString(sCommand := 'Explode') = E_IiotCommand.None, Message := 'unknown');
AssertTrue(Condition := F_IiotCmdKind(eCommand := E_IiotCommand.SpeedSp) = E_IiotCmdKind.Value,
    Message := 'kind value');
AssertTrue(Condition := F_IiotCmdKind(eCommand := E_IiotCommand.AckReq) = E_IiotCmdKind.Mask, Message := 'kind mask');
AssertTrue(Condition := F_IiotCmdKind(eCommand := E_IiotCommand.Start) = E_IiotCmdKind.Pulse, Message := 'kind pulse');
AssertEquals_STRING(Expected := 'not_whitelisted',
    Actual := F_IiotCmdReasonText(eReason := E_IiotCmdReason.NotWhitelisted),
                    Message := 'reason text');
AssertEquals_STRING(Expected := 'timeout', Actual := F_IiotCmdReasonText(eReason := E_IiotCmdReason.Timeout),
                    Message := 'timeout text');
AssertEquals_STRING(Expected := 'RejectedMode', Actual := F_IiotCmdResultText(iResult := 2), Message := 'cmd_result 2');
AssertEquals_STRING(Expected := 'RejectedCfg', Actual := F_IiotCmdResultText(iResult := 9), Message := 'cmd_result 9');
AssertEquals_STRING(Expected := '', Actual := F_IiotCmdResultText(iResult := 10),
    Message := 'SubstExpired is not a result');

coUnit.TEST_FINISHED();
