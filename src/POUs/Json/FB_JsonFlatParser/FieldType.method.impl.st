uiIdx := FindField(sKey := sKey);
IF uiIdx = 0 THEN
    FieldType := E_JsonType.Missing;
ELSE
    FieldType := aFields[uiIdx].eType;
END_IF
