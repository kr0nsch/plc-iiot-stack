uiIdx := FindField(sKey := sKey);
IF uiIdx > 0 THEN
    IF aFields[uiIdx].eType = E_JsonType.Number THEN
        lrValue := aFields[uiIdx].lrNumber;
        GetNumber := TRUE;
    END_IF
END_IF
