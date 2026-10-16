AppendKey(sKeyName := sKey);
IF xValue THEN
    AppendRaw(sText := 'true');
ELSE
    AppendRaw(sText := 'false');
END_IF
