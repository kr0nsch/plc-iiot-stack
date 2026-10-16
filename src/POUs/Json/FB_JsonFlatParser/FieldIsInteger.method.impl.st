uiIdx := FindField(sKey := sKey);
IF uiIdx > 0 THEN
    FieldIsInteger := aFields[uiIdx].eType = E_JsonType.Number AND aFields[uiIdx].xInteger;
END_IF
