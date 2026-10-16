lrTok := 0.0;
xTokInteger := FALSE;
IF Peek(sJson := sJson) = GVL_Const.ASCII_MINUS THEN
    xNegative := TRUE;
    uiPos := uiPos + 1;
END_IF
bCh := Peek(sJson := sJson);
IF bCh < GVL_Const.ASCII_ZERO OR bCh > GVL_Const.ASCII_NINE THEN
    Fail(eReason := E_JsonError.BadNumber);
    RETURN;
END_IF

// целая часть: 0 или цифры без ведущего нуля
IF bCh = GVL_Const.ASCII_ZERO THEN
    uiPos := uiPos + 1;
    uiDigits := 1;
    bCh := Peek(sJson := sJson);
    IF bCh >= GVL_Const.ASCII_ZERO AND bCh <= GVL_Const.ASCII_NINE THEN
        Fail(eReason := E_JsonError.BadNumber);
        RETURN;
    END_IF
ELSE
    WHILE bCh >= GVL_Const.ASCII_ZERO AND bCh <= GVL_Const.ASCII_NINE DO
        lrMantissa := lrMantissa * ULINT_TO_LREAL(GVL_Const.DECIMAL_BASE) + BYTE_TO_LREAL(bCh - GVL_Const.ASCII_ZERO);
        uiDigits := uiDigits + 1;
        uiPos := uiPos + 1;
        bCh := Peek(sJson := sJson);
    END_WHILE
END_IF

// дробная часть
IF bCh = GVL_Const.ASCII_DOT THEN
    uiPos := uiPos + 1;
    bCh := Peek(sJson := sJson);
    IF bCh < GVL_Const.ASCII_ZERO OR bCh > GVL_Const.ASCII_NINE THEN
        Fail(eReason := E_JsonError.BadNumber);
        RETURN;
    END_IF
    WHILE bCh >= GVL_Const.ASCII_ZERO AND bCh <= GVL_Const.ASCII_NINE DO
        lrMantissa := lrMantissa * ULINT_TO_LREAL(GVL_Const.DECIMAL_BASE) + BYTE_TO_LREAL(bCh - GVL_Const.ASCII_ZERO);
        uiDigits := uiDigits + 1;
        iFracDigits := iFracDigits + 1;
        uiPos := uiPos + 1;
        bCh := Peek(sJson := sJson);
    END_WHILE
END_IF
IF uiDigits > GVL_Const.JSON_MANTISSA_DIGITS_MAX THEN
    Fail(eReason := E_JsonError.BadNumber);
    RETURN;
END_IF

// порядок
IF bCh = GVL_Const.ASCII_LOWER_E OR bCh = GVL_Const.ASCII_UPPER_E THEN
    xHasExp := TRUE;
    uiPos := uiPos + 1;
    bCh := Peek(sJson := sJson);
    IF bCh = GVL_Const.ASCII_MINUS THEN
        xExpNegative := TRUE;
        uiPos := uiPos + 1;
    ELSIF bCh = GVL_Const.ASCII_PLUS THEN
        uiPos := uiPos + 1;
    END_IF
    bCh := Peek(sJson := sJson);
    IF bCh < GVL_Const.ASCII_ZERO OR bCh > GVL_Const.ASCII_NINE THEN
        Fail(eReason := E_JsonError.BadNumber);
        RETURN;
    END_IF
    WHILE bCh >= GVL_Const.ASCII_ZERO AND bCh <= GVL_Const.ASCII_NINE DO
        IF uiExpDigits >= GVL_Const.JSON_EXP_DIGITS_MAX THEN
            Fail(eReason := E_JsonError.BadNumber);
            RETURN;
        END_IF
        iExp := iExp * ULINT_TO_INT(GVL_Const.DECIMAL_BASE) + BYTE_TO_INT(bCh - GVL_Const.ASCII_ZERO);
        uiExpDigits := uiExpDigits + 1;
        uiPos := uiPos + 1;
        bCh := Peek(sJson := sJson);
    END_WHILE
    IF xExpNegative THEN
        iExp := -iExp;
    END_IF
END_IF

lrTok := lrMantissa * EXPT(ULINT_TO_LREAL(GVL_Const.DECIMAL_BASE), INT_TO_LREAL(iExp - iFracDigits));
xTokInteger := iFracDigits = 0 AND NOT xHasExp;
IF xNegative THEN
    lrTok := -lrTok;
END_IF
IF NOT (ABS(lrTok) <= GVL_Const.REAL_ABS_MAX) THEN
    Fail(eReason := E_JsonError.BadNumber);
    RETURN;
END_IF
ParseNumber := TRUE;
