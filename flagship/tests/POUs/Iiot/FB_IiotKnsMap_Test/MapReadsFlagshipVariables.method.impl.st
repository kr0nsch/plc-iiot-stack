coUnit.TEST('MapReadsFlagshipVariables');

xK1Saved := GVL_IO.xK1;
wAlmSaved := GVL_Station.stStationSts.wAlmActive;
eModeSaved := GVL_Station.stStationSts.eMode;
// реле K1 «Общая авария» под током — аварии нет: метрика K1/general_alarm = NOT GVL_IO.xK1
GVL_IO.xK1 := TRUE;
GVL_Station.stStationSts.wAlmActive := 16#0100;
GVL_Station.stStationSts.eMode := E_StationMode.Manual;
fbMap.FillPoints(aPointTable := aPoints);
fbMap.FillAlarmWords(aWordTable := aWords);
AssertEquals_LREAL(Expected := 0.0, Actual := aPoints[GVL_IiotMap.PT_K1_GENERAL_ALARM].lrValue, Delta := 0.0,
                   Message := 'K1 energized: no general alarm');
AssertEquals_LREAL(Expected := 2.0, Actual := aPoints[GVL_IiotMap.PT_KNS1_MODE].lrValue, Delta := 0.0,
                   Message := 'station mode Manual = 2');
AssertEquals_WORD(Expected := 16#0100, Actual := aWords[GVL_IiotMap.ALARM_WORDS_COUNT].wActive,
                  Message := 'station alarm word is the last row');
GVL_IO.xK1 := FALSE;
fbMap.FillPoints(aPointTable := aPoints);
AssertEquals_LREAL(Expected := 1.0, Actual := aPoints[GVL_IiotMap.PT_K1_GENERAL_ALARM].lrValue, Delta := 0.0,
                   Message := 'K1 released: general alarm');
GVL_IO.xK1 := xK1Saved;
GVL_Station.stStationSts.wAlmActive := wAlmSaved;
GVL_Station.stStationSts.eMode := eModeSaved;
// значения устройств и регулятора — из их структур состояния
AssertEquals_LREAL(Expected := REAL_TO_LREAL(GVL_Devices.fbLT101.stSts.rValue_eu),
                   Actual := aPoints[GVL_IiotMap.PT_LT101_LEVEL].lrValue, Delta := 0.0, Message := 'LT101 level');
AssertEquals_LREAL(Expected := REAL_TO_LREAL(GVL_Station.fbLIC101.stSts.rPv_eu),
                   Actual := aPoints[GVL_IiotMap.PT_LIC101_PV].lrValue, Delta := 0.0, Message := 'LIC101 pv');
AssertEquals_WORD(Expected := GVL_Devices.fbP101.stSts.stCommon.wAlmActive, Actual := aWords[1].wActive,
                  Message := 'P101 alarm word is the first row');

coUnit.TEST_FINISHED();
