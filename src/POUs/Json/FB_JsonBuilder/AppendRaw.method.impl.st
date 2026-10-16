uiTextLen := INT_TO_UINT(LEN(sText));
uiIdx := 0;
WHILE uiIdx < uiTextLen DO
    AppendByte(bChar := sText[uiIdx]);
    uiIdx := uiIdx + 1;
END_WHILE
