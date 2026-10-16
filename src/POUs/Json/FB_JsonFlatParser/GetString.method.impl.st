uiIdx := FindField(sKey := sKey);
IF uiIdx > 0 THEN
    IF aFields[uiIdx].eType = E_JsonType.Text THEN
        sValue := aFields[uiIdx].sText;
        GetString := TRUE;
    END_IF
END_IF
