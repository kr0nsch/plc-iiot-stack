uiTextLen := INT_TO_UINT(LEN(sText));
uiIdx := 0;
WHILE uiIdx < uiTextLen DO
    bCh := sText[uiIdx];
    IF bCh = GVL_Const.ASCII_QUOTE OR bCh = GVL_Const.ASCII_BACKSLASH THEN
        AppendByte(bChar := GVL_Const.ASCII_BACKSLASH);
        AppendByte(bChar := bCh);
    ELSIF bCh = GVL_Const.ASCII_LF THEN
        AppendByte(bChar := GVL_Const.ASCII_BACKSLASH);
        AppendByte(bChar := GVL_Const.ASCII_LOWER_N);
    ELSIF bCh = GVL_Const.ASCII_CR THEN
        AppendByte(bChar := GVL_Const.ASCII_BACKSLASH);
        AppendByte(bChar := GVL_Const.ASCII_LOWER_R);
    ELSIF bCh = GVL_Const.ASCII_TAB THEN
        AppendByte(bChar := GVL_Const.ASCII_BACKSLASH);
        AppendByte(bChar := GVL_Const.ASCII_LOWER_T);
    ELSIF bCh = GVL_Const.ASCII_BS THEN
        AppendByte(bChar := GVL_Const.ASCII_BACKSLASH);
        AppendByte(bChar := GVL_Const.ASCII_LOWER_B);
    ELSIF bCh = GVL_Const.ASCII_FF THEN
        AppendByte(bChar := GVL_Const.ASCII_BACKSLASH);
        AppendByte(bChar := GVL_Const.ASCII_LOWER_F);
    ELSIF bCh <= GVL_Const.ASCII_CTRL_LAST OR bCh > GVL_Const.ASCII_LAST THEN
        AppendByte(bChar := GVL_Const.ASCII_BACKSLASH);
        AppendByte(bChar := GVL_Const.ASCII_LOWER_U);
        AppendByte(bChar := GVL_Const.ASCII_ZERO);
        AppendByte(bChar := GVL_Const.ASCII_ZERO);
        AppendHexDigit(bNibble := SHR(bCh, GVL_Const.NIBBLE_BITS));
        AppendHexDigit(bNibble := bCh AND GVL_Const.NIBBLE_MASK);
    ELSE
        AppendByte(bChar := bCh);
    END_IF
    uiIdx := uiIdx + 1;
END_WHILE
