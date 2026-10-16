xRetained := FALSE;
IF uiRxCount = 0 THEN
    RETURN;
END_IF
sTopic := aRxTopic[1];
sPayload := aRxPayload[1];
xTruncated := aRxTruncated[1];
FOR uiIdx := 1 TO uiRxCount - 1 DO
    aRxTopic[uiIdx] := aRxTopic[uiIdx + 1];
    aRxPayload[uiIdx] := aRxPayload[uiIdx + 1];
    aRxTruncated[uiIdx] := aRxTruncated[uiIdx + 1];
END_FOR
uiRxCount := uiRxCount - 1;
Receive := TRUE;
