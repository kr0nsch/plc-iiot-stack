IF uiInCount >= IN_MAX THEN
    RETURN;
END_IF
uiInCount := uiInCount + 1;
aIn[uiInCount].sTopic := sTopic;
aIn[uiInCount].sPayload := sPayload;
aIn[uiInCount].xTruncated := xTruncated;
aIn[uiInCount].xRetained := xRetained;
Inject := TRUE;
