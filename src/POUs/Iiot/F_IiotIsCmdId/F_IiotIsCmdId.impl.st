iLen := LEN(sText);
IF iLen < UINT_TO_INT(GVL_Const.CMD_ID_MIN_LEN) OR iLen > UINT_TO_INT(GVL_Const.CMD_ID_LEN) THEN
    RETURN;
END_IF
FOR iIdx := 0 TO iLen - 1 DO
    bCh := sText[iIdx];
    IF NOT ((bCh >= GVL_Const.ASCII_UPPER_A AND bCh <= GVL_Const.ASCII_UPPER_Z)
            OR (bCh >= GVL_Const.ASCII_LOWER_A AND bCh <= GVL_Const.ASCII_LOWER_Z)
            OR (bCh >= GVL_Const.ASCII_ZERO AND bCh <= GVL_Const.ASCII_NINE)
            OR bCh = GVL_Const.ASCII_UNDERSCORE OR bCh = GVL_Const.ASCII_MINUS) THEN
        RETURN;
    END_IF
END_FOR
F_IiotIsCmdId := TRUE;
