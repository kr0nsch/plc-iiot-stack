diLo := LOWER_BOUND(aAlarmTable, 1);
diTotal := UPPER_BOUND(aAlarmTable, 1) - diLo + 1;
uiPending := 0;
IF diTotal <= 0 THEN
    RETURN;
END_IF
IF diCursor < 0 OR diCursor >= diTotal THEN
    diCursor := 0;
END_IF
uiBudget := MAX(uiMaxPerCycle, 1);
diNextCursor := -1;
FOR diStep := 0 TO diTotal - 1 DO
    diIdx := diLo + (diCursor + diStep) MOD diTotal;
    IF NOT aAlarmTable[diIdx].xSent OR aAlarmTable[diIdx].eState <> aAlarmTable[diIdx].eLastState THEN
        IF uiBudget > 0 AND NOT xBlocked THEN
            IF PublishAlarm(stAlarm := aAlarmTable[diIdx]) THEN
                uiBudget := uiBudget - 1;
            ELSE
                xBlocked := TRUE;
            END_IF
        END_IF
        IF NOT aAlarmTable[diIdx].xSent OR aAlarmTable[diIdx].eState <> aAlarmTable[diIdx].eLastState THEN
            uiPending := uiPending + 1;
            IF diNextCursor < 0 THEN
                diNextCursor := diIdx - diLo;
            END_IF
        END_IF
    END_IF
END_FOR
IF diNextCursor >= 0 THEN
    diCursor := diNextCursor;
END_IF
