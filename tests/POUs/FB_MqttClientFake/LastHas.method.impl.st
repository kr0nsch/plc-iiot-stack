uiIdx := FindLast(sTopic := sTopic);
IF uiIdx > 0 THEN
    LastHas := F_TestContains(sText := aPub[uiIdx].sPayload, sPart := sPart);
END_IF
