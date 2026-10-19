coUnit.TEST('MapTablesFollowSchema');

AssertEquals_DINT(Expected := 139, Actual := GVL_IiotMap.POINT_COUNT, Message := 'metrics in the catalog');
AssertEquals_DINT(Expected := 86, Actual := GVL_IiotMap.RULE_COUNT, Message := 'whitelist rows');
AssertEquals_DINT(Expected := 88, Actual := GVL_IiotMap.ALARM_COUNT, Message := 'alarms of the flagship');
AssertEquals_STRING(Expected := 'LT101/level', Actual := GVL_IiotMap.POINT_CFG[GVL_IiotMap.PT_LT101_LEVEL].sPath,
                    Message := 'LT101 level path');
AssertEquals_STRING(Expected := 'm', Actual := GVL_IiotMap.POINT_CFG[GVL_IiotMap.PT_LT101_LEVEL].sUnit,
    Message := 'unit');
AssertEquals_REAL(Expected := 0.01, Actual := GVL_IiotMap.POINT_CFG[GVL_IiotMap.PT_LT101_LEVEL].rDeadband,
    Delta := 1.0E-6, Message := 'deadband');
AssertTrue(Condition := GVL_IiotMap.POINT_CFG[GVL_IiotMap.PT_LT101_LEVEL].eKind = E_IiotValueKind.Analog,
           Message := 'analog');
AssertTrue(Condition := GVL_IiotMap.POINT_CFG[GVL_IiotMap.PT_P101_STATE].eKind = E_IiotValueKind.Integer,
           Message := 'enum is an integer');
AssertTrue(Condition := GVL_IiotMap.POINT_CFG[GVL_IiotMap.PT_PLC1_UPTIME].xPeriodicOnly,
    Message := 'uptime periodic only');
AssertEquals_STRING(Expected := 'P101', Actual := GVL_IiotMap.RULE_CFG[1].sDevice, Message := 'first rule device');
AssertTrue(Condition := GVL_IiotMap.RULE_CFG[1].eCommand = E_IiotCommand.SetAuto, Message := 'first rule command');
AssertEquals_UDINT(Expected := 110, Actual := GVL_IiotMap.ALARM_CFG[1].udiId, Message := 'first alarm id');
AssertEquals_STRING(Expected := 'FTS', Actual := GVL_IiotMap.ALARM_CFG[1].sSuffix, Message := 'first alarm suffix');

coUnit.TEST_FINISHED();
