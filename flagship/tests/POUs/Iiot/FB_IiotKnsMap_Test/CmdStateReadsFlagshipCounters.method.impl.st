coUnit.TEST('CmdStateReadsFlagshipCounters');

stStsSaved := GVL_Station.stStationSts;
GVL_Station.stStationSts.uiCmdSeq := 41;
GVL_Station.stStationSts.eCmdResult := PL.E_CmdResult.RejectedMode;
diDev := GVL_IiotMap.RULE_CFG[FindRule(sDevice := 'KNS1', eCommand := E_IiotCommand.SetAuto)].diDev;
fbMap.DeviceCmdState(diDev := diDev, uiSeq => uiSeq, iResult => iResult);
GVL_Station.stStationSts := stStsSaved;
AssertEquals_UINT(Expected := 41, Actual := uiSeq, Message := 'station uiCmdSeq');
AssertEquals_INT(Expected := 2, Actual := iResult, Message := 'station eCmdResult RejectedMode = 2');

diDev := GVL_IiotMap.RULE_CFG[FindRule(sDevice := 'LIC101', eCommand := E_IiotCommand.SetAuto)].diDev;
fbMap.DeviceCmdState(diDev := diDev, uiSeq => uiSeq, iResult => iResult);
AssertEquals_UINT(Expected := GVL_Station.fbLIC101.stSts.stCommon.uiCmdSeq, Actual := uiSeq,
                  Message := 'LIC101 uiCmdSeq');
AssertEquals_INT(Expected := TO_INT(GVL_Station.fbLIC101.stSts.stCommon.eCmdResult), Actual := iResult,
                 Message := 'LIC101 eCmdResult');

fbMap.DeviceCmdState(diDev := 0, uiSeq => uiSeq, iResult => iResult);
AssertEquals_UINT(Expected := 0, Actual := uiSeq, Message := 'unknown device: seq 0');
AssertEquals_INT(Expected := 0, Actual := iResult, Message := 'unknown device: result 0');

coUnit.TEST_FINISHED();
