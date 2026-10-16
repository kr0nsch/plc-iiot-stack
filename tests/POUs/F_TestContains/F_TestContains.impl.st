uiPartLen := INT_TO_UINT(LEN(sPart));
uiTextLen := 0;
WHILE uiTextLen < GVL_Const.MQTT_PAYLOAD_LEN AND_THEN sText[uiTextLen] <> 0 DO
    uiTextLen := uiTextLen + 1;
END_WHILE
IF uiPartLen = 0 THEN
    F_TestContains := TRUE;
    RETURN;
END_IF
IF uiPartLen > uiTextLen THEN
    RETURN;
END_IF
FOR uiStart := 0 TO uiTextLen - uiPartLen DO
    xMatch := TRUE;
    FOR uiIdx := 0 TO uiPartLen - 1 DO
        IF sText[uiStart + uiIdx] <> sPart[uiIdx] THEN
            xMatch := FALSE;
            EXIT;
        END_IF
    END_FOR
    IF xMatch THEN
        F_TestContains := TRUE;
        RETURN;
    END_IF
END_FOR
