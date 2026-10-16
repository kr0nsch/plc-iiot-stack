FOR diIdx := LOWER_BOUND(aAlarmTable, 1) TO UPPER_BOUND(aAlarmTable, 1) DO
    aAlarmTable[diIdx].xSent := FALSE;
END_FOR
uiPending := 0;
