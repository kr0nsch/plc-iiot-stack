FOR diIdx := LOWER_BOUND(aPointTable, 1) TO UPPER_BOUND(aPointTable, 1) DO
    aPointTable[diIdx].xSent := FALSE;
END_FOR
xPeriodRunning := FALSE;
uiPending := 0;
