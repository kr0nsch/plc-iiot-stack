FOR diIdx := UINT_TO_DINT(uiPubCount) TO 1 BY -1 DO
    IF aPub[diIdx].sTopic = sTopic THEN
        FindLast := DINT_TO_UINT(diIdx);
        RETURN;
    END_IF
END_FOR
