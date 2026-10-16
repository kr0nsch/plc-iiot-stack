IF uiInCount = 0 OR NOT IsConnected() THEN
    RETURN;
END_IF
sTopic := aIn[1].sTopic;
sPayload := aIn[1].sPayload;
xTruncated := aIn[1].xTruncated;
xRetained := aIn[1].xRetained;
FOR uiIdx := 1 TO uiInCount - 1 DO
    aIn[uiIdx] := aIn[uiIdx + 1];
END_FOR
uiInCount := uiInCount - 1;
Receive := TRUE;
