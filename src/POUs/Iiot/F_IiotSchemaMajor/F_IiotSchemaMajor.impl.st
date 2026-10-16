F_IiotSchemaMajor := -1;
iLen := LEN(sVersion);
FOR iIdx := 0 TO iLen - 1 DO
    bCh := sVersion[iIdx];
    IF bCh = GVL_Const.ASCII_DOT THEN
        IF iPart <> 0 OR iDigits = 0 THEN
            RETURN;
        END_IF
        iPart := 1;
        iDigits := 0;
        xLeadZero := FALSE;
    ELSIF bCh >= GVL_Const.ASCII_ZERO AND bCh <= GVL_Const.ASCII_NINE THEN
        IF xLeadZero THEN
            RETURN;          // 01, 1.01
        END_IF
        IF iDigits = 0 AND bCh = GVL_Const.ASCII_ZERO THEN
            xLeadZero := TRUE;
        END_IF
        IF iPart = 0 THEN
            iMajor := iMajor * ULINT_TO_INT(GVL_Const.DECIMAL_BASE) + BYTE_TO_INT(bCh - GVL_Const.ASCII_ZERO);
        END_IF
        iDigits := iDigits + 1;
        IF iDigits > UINT_TO_INT(GVL_Const.JSON_EXP_DIGITS_MAX) THEN
            RETURN;
        END_IF
    ELSE
        RETURN;
    END_IF
END_FOR
IF iPart = 1 AND iDigits > 0 THEN
    F_IiotSchemaMajor := iMajor;
END_IF
