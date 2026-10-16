FindField := 0;
FOR uiIdx := 1 TO uiCount DO
    IF aFields[uiIdx].sKey = sKey THEN
        FindField := uiIdx;
        RETURN;
    END_IF
END_FOR
