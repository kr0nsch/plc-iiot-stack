coUnit.TEST('StationRowsFollowFlagship');

AssertEquals_STRING(Expected := 'KNS1/mode', Actual := GVL_IiotMap.POINT_CFG[GVL_IiotMap.PT_KNS1_MODE].sPath,
                    Message := 'station mode path');
AssertEquals_STRING(Expected := 'LIC101/pv', Actual := GVL_IiotMap.POINT_CFG[GVL_IiotMap.PT_LIC101_PV].sPath,
                    Message := 'LIC101 pv path');
AssertEquals_STRING(Expected := 'KNS1', Actual := GVL_IiotMap.RULE_CFG[78].sDevice, Message := 'station rule device');
AssertTrue(Condition := GVL_IiotMap.RULE_CFG[84].eCommand = E_IiotCommand.Silence, Message := 'station Silence rule');
AssertEquals_UDINT(Expected := 100009, Actual := GVL_IiotMap.ALARM_CFG[84].udiId, Message := 'KNS1.NOAUTO id');
AssertEquals_STRING(Expected := 'NOAUTO', Actual := GVL_IiotMap.ALARM_CFG[84].sSuffix,
                    Message := 'six-letter suffix is not truncated');
AssertEquals_UINT(Expected := 8, Actual := GVL_IiotMap.ALARM_CFG[84].uiSlot, Message := 'station bit = slot - 1');
AssertEquals_DINT(Expected := GVL_IiotMap.ALARM_WORDS_COUNT, Actual := GVL_IiotMap.ALARM_CFG[84].diWords,
                  Message := 'station words are the last row');

coUnit.TEST_FINISHED();
