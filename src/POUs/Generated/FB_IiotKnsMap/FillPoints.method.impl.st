// Массив меньше перечня (не тот, что объявлен в PRG_Iiot): ничего не пишем, а не выходим за границы
IF LOWER_BOUND(aPointTable, 1) > 1 OR UPPER_BOUND(aPointTable, 1) < GVL_IiotMap.POINT_COUNT THEN
    RETURN;
END_IF
aPointTable[1].lrValue := BOOL_TO_LREAL(GVL_Devices.fbP101.xRunning);
aPointTable[1].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
aPointTable[2].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbP101.stSts.eState));
aPointTable[2].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
aPointTable[3].lrValue := REAL_TO_LREAL(GVL_Devices.fbP101.stSts.rSpeedAct_pct);
aPointTable[3].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
IF (GVL_Devices.fbP101.stSts.stCommon.wFault AND GVL_Const.MOT_FLT_COMM) <> 0
   OR (GVL_Devices.fbP101.stSts.stCommon.wWarning AND GVL_Const.MOT_WRN_COMM) <> 0 THEN
    aPointTable[3].eQuality := E_IiotQuality.Bad;
END_IF
aPointTable[4].lrValue := REAL_TO_LREAL(GVL_Devices.fbP101.stSts.rSpeedRef_pct);
aPointTable[4].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
aPointTable[5].lrValue := REAL_TO_LREAL(GVL_Devices.fbP101.stSts.rRunTime_h);
aPointTable[5].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
aPointTable[6].lrValue := UDINT_TO_LREAL(GVL_Devices.fbP101.stSts.udiStarts);
aPointTable[6].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
aPointTable[7].lrValue := UINT_TO_LREAL(GVL_Devices.fbP101.stSts.uiStartsLastHour);
aPointTable[7].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
aPointTable[8].lrValue := REAL_TO_LREAL(GVL_Devices.fbP101.stSts.rRunTimeMaint_h);
aPointTable[8].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
aPointTable[9].lrValue := UDINT_TO_LREAL(GVL_Devices.fbP101.stSts.udiStartsMaint);
aPointTable[9].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
aPointTable[10].lrValue := UINT_TO_LREAL(GVL_IO.uiP101_FCODE);
aPointTable[10].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
IF (GVL_Devices.fbP101.stSts.stCommon.wFault AND GVL_Const.MOT_FLT_COMM) <> 0
   OR (GVL_Devices.fbP101.stSts.stCommon.wWarning AND GVL_Const.MOT_WRN_COMM) <> 0 THEN
    aPointTable[10].eQuality := E_IiotQuality.Bad;
END_IF
aPointTable[11].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbP101.stSts.stCommon.eMode));
aPointTable[11].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
aPointTable[12].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
aPointTable[12].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP101.stSts.stCommon.eNe107));
aPointTable[13].lrValue := BOOL_TO_LREAL(GVL_Devices.fbP102.xRunning);
aPointTable[13].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
aPointTable[14].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbP102.stSts.eState));
aPointTable[14].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
aPointTable[15].lrValue := REAL_TO_LREAL(GVL_Devices.fbP102.stSts.rSpeedAct_pct);
aPointTable[15].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
IF (GVL_Devices.fbP102.stSts.stCommon.wFault AND GVL_Const.MOT_FLT_COMM) <> 0
   OR (GVL_Devices.fbP102.stSts.stCommon.wWarning AND GVL_Const.MOT_WRN_COMM) <> 0 THEN
    aPointTable[15].eQuality := E_IiotQuality.Bad;
END_IF
aPointTable[16].lrValue := REAL_TO_LREAL(GVL_Devices.fbP102.stSts.rSpeedRef_pct);
aPointTable[16].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
aPointTable[17].lrValue := REAL_TO_LREAL(GVL_Devices.fbP102.stSts.rRunTime_h);
aPointTable[17].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
aPointTable[18].lrValue := UDINT_TO_LREAL(GVL_Devices.fbP102.stSts.udiStarts);
aPointTable[18].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
aPointTable[19].lrValue := UINT_TO_LREAL(GVL_Devices.fbP102.stSts.uiStartsLastHour);
aPointTable[19].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
aPointTable[20].lrValue := REAL_TO_LREAL(GVL_Devices.fbP102.stSts.rRunTimeMaint_h);
aPointTable[20].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
aPointTable[21].lrValue := UDINT_TO_LREAL(GVL_Devices.fbP102.stSts.udiStartsMaint);
aPointTable[21].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
aPointTable[22].lrValue := UINT_TO_LREAL(GVL_IO.uiP102_FCODE);
aPointTable[22].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
IF (GVL_Devices.fbP102.stSts.stCommon.wFault AND GVL_Const.MOT_FLT_COMM) <> 0
   OR (GVL_Devices.fbP102.stSts.stCommon.wWarning AND GVL_Const.MOT_WRN_COMM) <> 0 THEN
    aPointTable[22].eQuality := E_IiotQuality.Bad;
END_IF
aPointTable[23].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbP102.stSts.stCommon.eMode));
aPointTable[23].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
aPointTable[24].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
aPointTable[24].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP102.stSts.stCommon.eNe107));
aPointTable[25].lrValue := BOOL_TO_LREAL(GVL_Devices.fbP103.xRunning);
aPointTable[25].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
aPointTable[26].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbP103.stSts.eState));
aPointTable[26].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
aPointTable[27].lrValue := REAL_TO_LREAL(GVL_Devices.fbP103.stSts.rSpeedAct_pct);
aPointTable[27].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
IF (GVL_Devices.fbP103.stSts.stCommon.wFault AND GVL_Const.MOT_FLT_COMM) <> 0
   OR (GVL_Devices.fbP103.stSts.stCommon.wWarning AND GVL_Const.MOT_WRN_COMM) <> 0 THEN
    aPointTable[27].eQuality := E_IiotQuality.Bad;
END_IF
aPointTable[28].lrValue := REAL_TO_LREAL(GVL_Devices.fbP103.stSts.rSpeedRef_pct);
aPointTable[28].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
aPointTable[29].lrValue := REAL_TO_LREAL(GVL_Devices.fbP103.stSts.rRunTime_h);
aPointTable[29].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
aPointTable[30].lrValue := UDINT_TO_LREAL(GVL_Devices.fbP103.stSts.udiStarts);
aPointTable[30].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
aPointTable[31].lrValue := UINT_TO_LREAL(GVL_Devices.fbP103.stSts.uiStartsLastHour);
aPointTable[31].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
aPointTable[32].lrValue := REAL_TO_LREAL(GVL_Devices.fbP103.stSts.rRunTimeMaint_h);
aPointTable[32].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
aPointTable[33].lrValue := UDINT_TO_LREAL(GVL_Devices.fbP103.stSts.udiStartsMaint);
aPointTable[33].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
aPointTable[34].lrValue := UINT_TO_LREAL(GVL_IO.uiP103_FCODE);
aPointTable[34].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
IF (GVL_Devices.fbP103.stSts.stCommon.wFault AND GVL_Const.MOT_FLT_COMM) <> 0
   OR (GVL_Devices.fbP103.stSts.stCommon.wWarning AND GVL_Const.MOT_WRN_COMM) <> 0 THEN
    aPointTable[34].eQuality := E_IiotQuality.Bad;
END_IF
aPointTable[35].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbP103.stSts.stCommon.eMode));
aPointTable[35].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
aPointTable[36].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
aPointTable[36].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbP103.stSts.stCommon.eNe107));
aPointTable[37].lrValue := BOOL_TO_LREAL(GVL_Devices.fbV1.xRunning);
aPointTable[37].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbV1.stSts.stCommon.eNe107));
aPointTable[38].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbV1.stSts.eState));
aPointTable[38].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbV1.stSts.stCommon.eNe107));
aPointTable[39].lrValue := REAL_TO_LREAL(GVL_Devices.fbV1.stSts.rRunTime_h);
aPointTable[39].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbV1.stSts.stCommon.eNe107));
aPointTable[40].lrValue := UDINT_TO_LREAL(GVL_Devices.fbV1.stSts.udiStarts);
aPointTable[40].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbV1.stSts.stCommon.eNe107));
aPointTable[41].lrValue := UINT_TO_LREAL(GVL_Devices.fbV1.stSts.uiStartsLastHour);
aPointTable[41].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbV1.stSts.stCommon.eNe107));
aPointTable[42].lrValue := REAL_TO_LREAL(GVL_Devices.fbV1.stSts.rRunTimeMaint_h);
aPointTable[42].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbV1.stSts.stCommon.eNe107));
aPointTable[43].lrValue := UDINT_TO_LREAL(GVL_Devices.fbV1.stSts.udiStartsMaint);
aPointTable[43].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbV1.stSts.stCommon.eNe107));
aPointTable[44].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbV1.stSts.stCommon.eMode));
aPointTable[44].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbV1.stSts.stCommon.eNe107));
aPointTable[45].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbV1.stSts.stCommon.eNe107));
aPointTable[45].eQuality := F_IiotQuality(xValid := TRUE, iNe107 := TO_INT(GVL_Devices.fbV1.stSts.stCommon.eNe107));
aPointTable[46].lrValue := REAL_TO_LREAL(GVL_Devices.fbLT101.stSts.rValue_eu);
aPointTable[46].eQuality := F_IiotQuality(xValid := GVL_Devices.fbLT101.xValid,
    iNe107 := TO_INT(GVL_Devices.fbLT101.stSts.stCommon.eNe107));
aPointTable[47].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbLT101.stSts.stCommon.eMode));
aPointTable[47].eQuality := F_IiotQuality(xValid := GVL_Devices.fbLT101.xValid,
    iNe107 := TO_INT(GVL_Devices.fbLT101.stSts.stCommon.eNe107));
aPointTable[48].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbLT101.stSts.stCommon.eNe107));
aPointTable[48].eQuality := F_IiotQuality(xValid := GVL_Devices.fbLT101.xValid,
    iNe107 := TO_INT(GVL_Devices.fbLT101.stSts.stCommon.eNe107));
aPointTable[49].lrValue := BOOL_TO_LREAL(GVL_Devices.fbLS102.xValue);
aPointTable[49].eQuality := F_IiotQuality(xValid := GVL_Devices.fbLS102.xValid,
    iNe107 := TO_INT(GVL_Devices.fbLS102.stSts.stCommon.eNe107));
aPointTable[50].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbLS102.stSts.stCommon.eMode));
aPointTable[50].eQuality := F_IiotQuality(xValid := GVL_Devices.fbLS102.xValid,
    iNe107 := TO_INT(GVL_Devices.fbLS102.stSts.stCommon.eNe107));
aPointTable[51].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbLS102.stSts.stCommon.eNe107));
aPointTable[51].eQuality := F_IiotQuality(xValid := GVL_Devices.fbLS102.xValid,
    iNe107 := TO_INT(GVL_Devices.fbLS102.stSts.stCommon.eNe107));
aPointTable[52].lrValue := BOOL_TO_LREAL(GVL_Devices.fbLS103.xValue);
aPointTable[52].eQuality := F_IiotQuality(xValid := GVL_Devices.fbLS103.xValid,
    iNe107 := TO_INT(GVL_Devices.fbLS103.stSts.stCommon.eNe107));
aPointTable[53].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbLS103.stSts.stCommon.eMode));
aPointTable[53].eQuality := F_IiotQuality(xValid := GVL_Devices.fbLS103.xValid,
    iNe107 := TO_INT(GVL_Devices.fbLS103.stSts.stCommon.eNe107));
aPointTable[54].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbLS103.stSts.stCommon.eNe107));
aPointTable[54].eQuality := F_IiotQuality(xValid := GVL_Devices.fbLS103.xValid,
    iNe107 := TO_INT(GVL_Devices.fbLS103.stSts.stCommon.eNe107));
aPointTable[55].lrValue := REAL_TO_LREAL(GVL_Devices.fbIT111.stSts.rValue_eu);
aPointTable[55].eQuality := F_IiotQuality(xValid := GVL_Devices.fbIT111.xValid,
    iNe107 := TO_INT(GVL_Devices.fbIT111.stSts.stCommon.eNe107));
aPointTable[56].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbIT111.stSts.stCommon.eMode));
aPointTable[56].eQuality := F_IiotQuality(xValid := GVL_Devices.fbIT111.xValid,
    iNe107 := TO_INT(GVL_Devices.fbIT111.stSts.stCommon.eNe107));
aPointTable[57].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbIT111.stSts.stCommon.eNe107));
aPointTable[57].eQuality := F_IiotQuality(xValid := GVL_Devices.fbIT111.xValid,
    iNe107 := TO_INT(GVL_Devices.fbIT111.stSts.stCommon.eNe107));
aPointTable[58].lrValue := BOOL_TO_LREAL(GVL_Devices.fbTS112.xValue);
aPointTable[58].eQuality := F_IiotQuality(xValid := GVL_Devices.fbTS112.xValid,
    iNe107 := TO_INT(GVL_Devices.fbTS112.stSts.stCommon.eNe107));
aPointTable[59].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbTS112.stSts.stCommon.eMode));
aPointTable[59].eQuality := F_IiotQuality(xValid := GVL_Devices.fbTS112.xValid,
    iNe107 := TO_INT(GVL_Devices.fbTS112.stSts.stCommon.eNe107));
aPointTable[60].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbTS112.stSts.stCommon.eNe107));
aPointTable[60].eQuality := F_IiotQuality(xValid := GVL_Devices.fbTS112.xValid,
    iNe107 := TO_INT(GVL_Devices.fbTS112.stSts.stCommon.eNe107));
aPointTable[61].lrValue := BOOL_TO_LREAL(GVL_Devices.fbMS113.xValue);
aPointTable[61].eQuality := F_IiotQuality(xValid := GVL_Devices.fbMS113.xValid,
    iNe107 := TO_INT(GVL_Devices.fbMS113.stSts.stCommon.eNe107));
aPointTable[62].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbMS113.stSts.stCommon.eMode));
aPointTable[62].eQuality := F_IiotQuality(xValid := GVL_Devices.fbMS113.xValid,
    iNe107 := TO_INT(GVL_Devices.fbMS113.stSts.stCommon.eNe107));
aPointTable[63].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbMS113.stSts.stCommon.eNe107));
aPointTable[63].eQuality := F_IiotQuality(xValid := GVL_Devices.fbMS113.xValid,
    iNe107 := TO_INT(GVL_Devices.fbMS113.stSts.stCommon.eNe107));
aPointTable[64].lrValue := REAL_TO_LREAL(GVL_Devices.fbIT121.stSts.rValue_eu);
aPointTable[64].eQuality := F_IiotQuality(xValid := GVL_Devices.fbIT121.xValid,
    iNe107 := TO_INT(GVL_Devices.fbIT121.stSts.stCommon.eNe107));
aPointTable[65].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbIT121.stSts.stCommon.eMode));
aPointTable[65].eQuality := F_IiotQuality(xValid := GVL_Devices.fbIT121.xValid,
    iNe107 := TO_INT(GVL_Devices.fbIT121.stSts.stCommon.eNe107));
aPointTable[66].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbIT121.stSts.stCommon.eNe107));
aPointTable[66].eQuality := F_IiotQuality(xValid := GVL_Devices.fbIT121.xValid,
    iNe107 := TO_INT(GVL_Devices.fbIT121.stSts.stCommon.eNe107));
aPointTable[67].lrValue := BOOL_TO_LREAL(GVL_Devices.fbTS122.xValue);
aPointTable[67].eQuality := F_IiotQuality(xValid := GVL_Devices.fbTS122.xValid,
    iNe107 := TO_INT(GVL_Devices.fbTS122.stSts.stCommon.eNe107));
aPointTable[68].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbTS122.stSts.stCommon.eMode));
aPointTable[68].eQuality := F_IiotQuality(xValid := GVL_Devices.fbTS122.xValid,
    iNe107 := TO_INT(GVL_Devices.fbTS122.stSts.stCommon.eNe107));
aPointTable[69].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbTS122.stSts.stCommon.eNe107));
aPointTable[69].eQuality := F_IiotQuality(xValid := GVL_Devices.fbTS122.xValid,
    iNe107 := TO_INT(GVL_Devices.fbTS122.stSts.stCommon.eNe107));
aPointTable[70].lrValue := BOOL_TO_LREAL(GVL_Devices.fbMS123.xValue);
aPointTable[70].eQuality := F_IiotQuality(xValid := GVL_Devices.fbMS123.xValid,
    iNe107 := TO_INT(GVL_Devices.fbMS123.stSts.stCommon.eNe107));
aPointTable[71].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbMS123.stSts.stCommon.eMode));
aPointTable[71].eQuality := F_IiotQuality(xValid := GVL_Devices.fbMS123.xValid,
    iNe107 := TO_INT(GVL_Devices.fbMS123.stSts.stCommon.eNe107));
aPointTable[72].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbMS123.stSts.stCommon.eNe107));
aPointTable[72].eQuality := F_IiotQuality(xValid := GVL_Devices.fbMS123.xValid,
    iNe107 := TO_INT(GVL_Devices.fbMS123.stSts.stCommon.eNe107));
aPointTable[73].lrValue := REAL_TO_LREAL(GVL_Devices.fbIT131.stSts.rValue_eu);
aPointTable[73].eQuality := F_IiotQuality(xValid := GVL_Devices.fbIT131.xValid,
    iNe107 := TO_INT(GVL_Devices.fbIT131.stSts.stCommon.eNe107));
aPointTable[74].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbIT131.stSts.stCommon.eMode));
aPointTable[74].eQuality := F_IiotQuality(xValid := GVL_Devices.fbIT131.xValid,
    iNe107 := TO_INT(GVL_Devices.fbIT131.stSts.stCommon.eNe107));
aPointTable[75].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbIT131.stSts.stCommon.eNe107));
aPointTable[75].eQuality := F_IiotQuality(xValid := GVL_Devices.fbIT131.xValid,
    iNe107 := TO_INT(GVL_Devices.fbIT131.stSts.stCommon.eNe107));
aPointTable[76].lrValue := BOOL_TO_LREAL(GVL_Devices.fbTS132.xValue);
aPointTable[76].eQuality := F_IiotQuality(xValid := GVL_Devices.fbTS132.xValid,
    iNe107 := TO_INT(GVL_Devices.fbTS132.stSts.stCommon.eNe107));
aPointTable[77].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbTS132.stSts.stCommon.eMode));
aPointTable[77].eQuality := F_IiotQuality(xValid := GVL_Devices.fbTS132.xValid,
    iNe107 := TO_INT(GVL_Devices.fbTS132.stSts.stCommon.eNe107));
aPointTable[78].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbTS132.stSts.stCommon.eNe107));
aPointTable[78].eQuality := F_IiotQuality(xValid := GVL_Devices.fbTS132.xValid,
    iNe107 := TO_INT(GVL_Devices.fbTS132.stSts.stCommon.eNe107));
aPointTable[79].lrValue := BOOL_TO_LREAL(GVL_Devices.fbMS133.xValue);
aPointTable[79].eQuality := F_IiotQuality(xValid := GVL_Devices.fbMS133.xValid,
    iNe107 := TO_INT(GVL_Devices.fbMS133.stSts.stCommon.eNe107));
aPointTable[80].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbMS133.stSts.stCommon.eMode));
aPointTable[80].eQuality := F_IiotQuality(xValid := GVL_Devices.fbMS133.xValid,
    iNe107 := TO_INT(GVL_Devices.fbMS133.stSts.stCommon.eNe107));
aPointTable[81].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbMS133.stSts.stCommon.eNe107));
aPointTable[81].eQuality := F_IiotQuality(xValid := GVL_Devices.fbMS133.xValid,
    iNe107 := TO_INT(GVL_Devices.fbMS133.stSts.stCommon.eNe107));
aPointTable[82].lrValue := REAL_TO_LREAL(GVL_Devices.fbPT201.stSts.rValue_eu);
aPointTable[82].eQuality := F_IiotQuality(xValid := GVL_Devices.fbPT201.xValid,
    iNe107 := TO_INT(GVL_Devices.fbPT201.stSts.stCommon.eNe107));
aPointTable[83].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbPT201.stSts.stCommon.eMode));
aPointTable[83].eQuality := F_IiotQuality(xValid := GVL_Devices.fbPT201.xValid,
    iNe107 := TO_INT(GVL_Devices.fbPT201.stSts.stCommon.eNe107));
aPointTable[84].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbPT201.stSts.stCommon.eNe107));
aPointTable[84].eQuality := F_IiotQuality(xValid := GVL_Devices.fbPT201.xValid,
    iNe107 := TO_INT(GVL_Devices.fbPT201.stSts.stCommon.eNe107));
aPointTable[85].lrValue := REAL_TO_LREAL(GVL_Devices.fbFT202.stSts.rValue_eu);
aPointTable[85].eQuality := F_IiotQuality(xValid := GVL_Devices.fbFT202.xValid,
    iNe107 := TO_INT(GVL_Devices.fbFT202.stSts.stCommon.eNe107));
aPointTable[86].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbFT202.stSts.stCommon.eMode));
aPointTable[86].eQuality := F_IiotQuality(xValid := GVL_Devices.fbFT202.xValid,
    iNe107 := TO_INT(GVL_Devices.fbFT202.stSts.stCommon.eNe107));
aPointTable[87].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbFT202.stSts.stCommon.eNe107));
aPointTable[87].eQuality := F_IiotQuality(xValid := GVL_Devices.fbFT202.xValid,
    iNe107 := TO_INT(GVL_Devices.fbFT202.stSts.stCommon.eNe107));
aPointTable[88].lrValue := BOOL_TO_LREAL(GVL_Devices.fbLS203.xValue);
aPointTable[88].eQuality := F_IiotQuality(xValid := GVL_Devices.fbLS203.xValid,
    iNe107 := TO_INT(GVL_Devices.fbLS203.stSts.stCommon.eNe107));
aPointTable[89].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbLS203.stSts.stCommon.eMode));
aPointTable[89].eQuality := F_IiotQuality(xValid := GVL_Devices.fbLS203.xValid,
    iNe107 := TO_INT(GVL_Devices.fbLS203.stSts.stCommon.eNe107));
aPointTable[90].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbLS203.stSts.stCommon.eNe107));
aPointTable[90].eQuality := F_IiotQuality(xValid := GVL_Devices.fbLS203.xValid,
    iNe107 := TO_INT(GVL_Devices.fbLS203.stSts.stCommon.eNe107));
aPointTable[91].lrValue := BOOL_TO_LREAL(GVL_Devices.fbES301.xValue);
aPointTable[91].eQuality := F_IiotQuality(xValid := GVL_Devices.fbES301.xValid,
    iNe107 := TO_INT(GVL_Devices.fbES301.stSts.stCommon.eNe107));
aPointTable[92].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbES301.stSts.stCommon.eMode));
aPointTable[92].eQuality := F_IiotQuality(xValid := GVL_Devices.fbES301.xValid,
    iNe107 := TO_INT(GVL_Devices.fbES301.stSts.stCommon.eNe107));
aPointTable[93].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbES301.stSts.stCommon.eNe107));
aPointTable[93].eQuality := F_IiotQuality(xValid := GVL_Devices.fbES301.xValid,
    iNe107 := TO_INT(GVL_Devices.fbES301.stSts.stCommon.eNe107));
aPointTable[94].lrValue := BOOL_TO_LREAL(GVL_Devices.fbYS302.xValue);
aPointTable[94].eQuality := F_IiotQuality(xValid := GVL_Devices.fbYS302.xValid,
    iNe107 := TO_INT(GVL_Devices.fbYS302.stSts.stCommon.eNe107));
aPointTable[95].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbYS302.stSts.stCommon.eMode));
aPointTable[95].eQuality := F_IiotQuality(xValid := GVL_Devices.fbYS302.xValid,
    iNe107 := TO_INT(GVL_Devices.fbYS302.stSts.stCommon.eNe107));
aPointTable[96].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbYS302.stSts.stCommon.eNe107));
aPointTable[96].eQuality := F_IiotQuality(xValid := GVL_Devices.fbYS302.xValid,
    iNe107 := TO_INT(GVL_Devices.fbYS302.stSts.stCommon.eNe107));
aPointTable[97].lrValue := BOOL_TO_LREAL(GVL_Devices.fbYS303.xValue);
aPointTable[97].eQuality := F_IiotQuality(xValid := GVL_Devices.fbYS303.xValid,
    iNe107 := TO_INT(GVL_Devices.fbYS303.stSts.stCommon.eNe107));
aPointTable[98].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbYS303.stSts.stCommon.eMode));
aPointTable[98].eQuality := F_IiotQuality(xValid := GVL_Devices.fbYS303.xValid,
    iNe107 := TO_INT(GVL_Devices.fbYS303.stSts.stCommon.eNe107));
aPointTable[99].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbYS303.stSts.stCommon.eNe107));
aPointTable[99].eQuality := F_IiotQuality(xValid := GVL_Devices.fbYS303.xValid,
    iNe107 := TO_INT(GVL_Devices.fbYS303.stSts.stCommon.eNe107));
aPointTable[100].lrValue := REAL_TO_LREAL(GVL_Devices.fbAT401.stSts.rValue_eu);
aPointTable[100].eQuality := F_IiotQuality(xValid := GVL_Devices.fbAT401.xValid,
    iNe107 := TO_INT(GVL_Devices.fbAT401.stSts.stCommon.eNe107));
aPointTable[101].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbAT401.stSts.stCommon.eMode));
aPointTable[101].eQuality := F_IiotQuality(xValid := GVL_Devices.fbAT401.xValid,
    iNe107 := TO_INT(GVL_Devices.fbAT401.stSts.stCommon.eNe107));
aPointTable[102].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbAT401.stSts.stCommon.eNe107));
aPointTable[102].eQuality := F_IiotQuality(xValid := GVL_Devices.fbAT401.xValid,
    iNe107 := TO_INT(GVL_Devices.fbAT401.stSts.stCommon.eNe107));
aPointTable[103].lrValue := REAL_TO_LREAL(GVL_Devices.fbAT402.stSts.rValue_eu);
aPointTable[103].eQuality := F_IiotQuality(xValid := GVL_Devices.fbAT402.xValid,
    iNe107 := TO_INT(GVL_Devices.fbAT402.stSts.stCommon.eNe107));
aPointTable[104].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbAT402.stSts.stCommon.eMode));
aPointTable[104].eQuality := F_IiotQuality(xValid := GVL_Devices.fbAT402.xValid,
    iNe107 := TO_INT(GVL_Devices.fbAT402.stSts.stCommon.eNe107));
aPointTable[105].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbAT402.stSts.stCommon.eNe107));
aPointTable[105].eQuality := F_IiotQuality(xValid := GVL_Devices.fbAT402.xValid,
    iNe107 := TO_INT(GVL_Devices.fbAT402.stSts.stCommon.eNe107));
aPointTable[106].lrValue := REAL_TO_LREAL(GVL_Devices.fbTT403.stSts.rValue_eu);
aPointTable[106].eQuality := F_IiotQuality(xValid := GVL_Devices.fbTT403.xValid,
    iNe107 := TO_INT(GVL_Devices.fbTT403.stSts.stCommon.eNe107));
aPointTable[107].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbTT403.stSts.stCommon.eMode));
aPointTable[107].eQuality := F_IiotQuality(xValid := GVL_Devices.fbTT403.xValid,
    iNe107 := TO_INT(GVL_Devices.fbTT403.stSts.stCommon.eNe107));
aPointTable[108].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbTT403.stSts.stCommon.eNe107));
aPointTable[108].eQuality := F_IiotQuality(xValid := GVL_Devices.fbTT403.xValid,
    iNe107 := TO_INT(GVL_Devices.fbTT403.stSts.stCommon.eNe107));
aPointTable[109].lrValue := BOOL_TO_LREAL(GVL_Devices.fbZS404.xValue);
aPointTable[109].eQuality := F_IiotQuality(xValid := GVL_Devices.fbZS404.xValid,
    iNe107 := TO_INT(GVL_Devices.fbZS404.stSts.stCommon.eNe107));
aPointTable[110].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbZS404.stSts.stCommon.eMode));
aPointTable[110].eQuality := F_IiotQuality(xValid := GVL_Devices.fbZS404.xValid,
    iNe107 := TO_INT(GVL_Devices.fbZS404.stSts.stCommon.eNe107));
aPointTable[111].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbZS404.stSts.stCommon.eNe107));
aPointTable[111].eQuality := F_IiotQuality(xValid := GVL_Devices.fbZS404.xValid,
    iNe107 := TO_INT(GVL_Devices.fbZS404.stSts.stCommon.eNe107));
aPointTable[112].lrValue := BOOL_TO_LREAL(GVL_Devices.fbYS405.xValue);
aPointTable[112].eQuality := F_IiotQuality(xValid := GVL_Devices.fbYS405.xValid,
    iNe107 := TO_INT(GVL_Devices.fbYS405.stSts.stCommon.eNe107));
aPointTable[113].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbYS405.stSts.stCommon.eMode));
aPointTable[113].eQuality := F_IiotQuality(xValid := GVL_Devices.fbYS405.xValid,
    iNe107 := TO_INT(GVL_Devices.fbYS405.stSts.stCommon.eNe107));
aPointTable[114].lrValue := INT_TO_LREAL(TO_INT(GVL_Devices.fbYS405.stSts.stCommon.eNe107));
aPointTable[114].eQuality := F_IiotQuality(xValid := GVL_Devices.fbYS405.xValid,
    iNe107 := TO_INT(GVL_Devices.fbYS405.stSts.stCommon.eNe107));
aPointTable[115].lrValue := BOOL_TO_LREAL(GVL_IO.xK1);
aPointTable[115].eQuality := E_IiotQuality.Good;
