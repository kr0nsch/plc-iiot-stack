uiIdx := FindLast(sTopic := sTopic);
IF uiIdx > 0 THEN
    LastPayload := aPub[uiIdx].sPayload;
ELSE
    LastPayload := '<none>';
END_IF
