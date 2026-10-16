uiIdx := FindLast(sTopic := sTopic);
IF uiIdx > 0 THEN
    LastIs := aPub[uiIdx].sPayload = sExpected;
END_IF
