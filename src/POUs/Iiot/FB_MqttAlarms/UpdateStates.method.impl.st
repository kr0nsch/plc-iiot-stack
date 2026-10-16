FOR diIdx := LOWER_BOUND(aAlarmTable, 1) TO UPPER_BOUND(aAlarmTable, 1) DO
    diWords := aAlarmTable[diIdx].stCfg.diWords;
    IF diWords >= LOWER_BOUND(aWordTable, 1) AND diWords <= UPPER_BOUND(aWordTable, 1) THEN
        aAlarmTable[diIdx].eState := F_IiotAlarmStateOf(stWords := aWordTable[diWords],
                                                        uiSlot := aAlarmTable[diIdx].stCfg.uiSlot);
    ELSE
        aAlarmTable[diIdx].eState := E_IiotAlarmState.Normal;
    END_IF
END_FOR
