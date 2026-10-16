uiIdx := FindField(sKey := sKey);
IF uiIdx > 0 THEN
    IF aFields[uiIdx].eType = E_JsonType.Boolean THEN
        xValue := aFields[uiIdx].xBool;
        GetBool := TRUE;
    END_IF
END_IF
