coUnit.TEST('CommandsGoToFlagshipCmdStructs');

stP102Saved := GVL_Hmi.stP102Cmd;
stP103Saved := GVL_Hmi.stP103Cmd;
stStationSaved := GVL_Station.stStationCmd;
stLic101Saved := GVL_Station.stLIC101Cmd;
GVL_Hmi.stP102Cmd.xStart := FALSE;
GVL_Station.stStationCmd.xSetLevelPid := FALSE;
GVL_Station.stLIC101Cmd.stCommon.xSetManual := FALSE;

diRule := FindRule(sDevice := 'P102', eCommand := E_IiotCommand.Start);
AssertTrue(Condition := diRule > 0 AND_THEN fbMap.ApplyCommand(diRule := diRule, rValue := 0.0),
           Message := 'P102 Start');
AssertTrue(Condition := GVL_Hmi.stP102Cmd.xStart, Message := 'P102 Start -> GVL_Hmi.stP102Cmd.xStart');
diRule := FindRule(sDevice := 'P103', eCommand := E_IiotCommand.SpeedSp);
AssertTrue(Condition := diRule > 0 AND_THEN fbMap.ApplyCommand(diRule := diRule, rValue := 70.0),
           Message := 'P103 SpeedSp');
AssertEquals_REAL(Expected := 70.0, Actual := GVL_Hmi.stP103Cmd.rSpeedSp_pct, Delta := 0.0,
                  Message := 'P103 SpeedSp -> GVL_Hmi.stP103Cmd.rSpeedSp_pct');
diRule := FindRule(sDevice := 'KNS1', eCommand := E_IiotCommand.SetLevelPid);
AssertTrue(Condition := diRule > 0 AND_THEN fbMap.ApplyCommand(diRule := diRule, rValue := 0.0),
           Message := 'KNS1 SetLevelPid');
AssertTrue(Condition := GVL_Station.stStationCmd.xSetLevelPid,
           Message := 'KNS1 SetLevelPid -> GVL_Station.stStationCmd.xSetLevelPid');
diRule := FindRule(sDevice := 'LIC101', eCommand := E_IiotCommand.SetManual);
AssertTrue(Condition := diRule > 0 AND_THEN fbMap.ApplyCommand(diRule := diRule, rValue := 0.0),
           Message := 'LIC101 SetManual');
AssertTrue(Condition := GVL_Station.stLIC101Cmd.stCommon.xSetManual,
           Message := 'LIC101 SetManual -> GVL_Station.stLIC101Cmd.stCommon.xSetManual');
AssertFalse(Condition := fbMap.ApplyCommand(diRule := 0, rValue := 0.0), Message := 'row 0');
AssertFalse(Condition := fbMap.ApplyCommand(diRule := GVL_IiotMap.RULE_COUNT + 1, rValue := 0.0),
            Message := 'row after the table');

GVL_Hmi.stP102Cmd := stP102Saved;
GVL_Hmi.stP103Cmd := stP103Saved;
GVL_Station.stStationCmd := stStationSaved;
GVL_Station.stLIC101Cmd := stLic101Saved;

coUnit.TEST_FINISHED();
