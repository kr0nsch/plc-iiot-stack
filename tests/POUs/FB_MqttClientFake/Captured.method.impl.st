FOR uiIdx := 1 TO CAPTURE_MAX DO
    IF LEN(aCapture[uiIdx]) > 0 THEN
        xAny := TRUE;
        IF aCapture[uiIdx] = sTopicIn THEN
            Captured := TRUE;
            RETURN;
        END_IF
    END_IF
END_FOR
Captured := NOT xAny;
