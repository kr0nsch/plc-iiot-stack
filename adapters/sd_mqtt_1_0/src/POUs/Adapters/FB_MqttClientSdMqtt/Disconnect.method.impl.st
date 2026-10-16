xEnable := FALSE;
xSubscribe := FALSE;
uiRxCount := 0;
FOR uiSlot := 1 TO PUB_POOL DO
    aPubState[uiSlot] := SLOT_FREE;
END_FOR
Disconnect := TRUE;
