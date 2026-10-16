iLen := LEN(sText);
IF iLen < 1 OR iLen > iMaxLen THEN
    RETURN;
END_IF
FOR iIdx := 0 TO iLen - 1 DO
    bCh := sText[iIdx];
    xUpper := bCh >= GVL_Const.ASCII_UPPER_A AND bCh <= GVL_Const.ASCII_UPPER_Z;
    xLower := bCh >= GVL_Const.ASCII_LOWER_A AND bCh <= GVL_Const.ASCII_LOWER_Z AND NOT xUpperOnly;
    xDigit := bCh >= GVL_Const.ASCII_ZERO AND bCh <= GVL_Const.ASCII_NINE;
    IF iIdx = 0 THEN
        IF NOT (xUpper OR xLower) THEN
            RETURN;
        END_IF
    ELSIF NOT (xUpper OR xLower OR xDigit OR bCh = GVL_Const.ASCII_UNDERSCORE) THEN
        RETURN;
    END_IF
END_FOR
F_IiotIsName := TRUE;
