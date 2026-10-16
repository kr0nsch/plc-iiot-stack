IF NOT F_IsFiniteLreal(lrValue := lrNumber) THEN
    AppendRaw(sText := 'null');
    RETURN;
END_IF
uiDecimals := MIN(uiDecimalsMax, GVL_Const.JSON_REAL_DECIMALS_MAX);
uliScale := 1;
FOR uiIdx := 1 TO uiDecimals DO
    uliScale := uliScale * GVL_Const.DECIMAL_BASE;
END_FOR
lrScaled := ABS(lrNumber) * ULINT_TO_LREAL(uliScale);
IF lrScaled >= GVL_Const.JSON_NUM_SCALED_MAX THEN
    AppendRaw(sText := 'null');
    RETURN;
END_IF
// преобразование LREAL -> ULINT в CODESYS округляет до ближайшего целого
uliScaled := LREAL_TO_ULINT(lrScaled);
IF lrNumber < 0.0 AND uliScaled > 0 THEN
    AppendByte(bChar := GVL_Const.ASCII_MINUS);
END_IF
AppendUlint(uliNumber := uliScaled / uliScale);
uliFrac := uliScaled MOD uliScale;
IF uliFrac > 0 THEN
    AppendByte(bChar := GVL_Const.ASCII_DOT);
    uiFracDigits := uiDecimals;
    WHILE (uliFrac MOD GVL_Const.DECIMAL_BASE) = 0 DO
        uliFrac := uliFrac / GVL_Const.DECIMAL_BASE;
        uiFracDigits := uiFracDigits - 1;
    END_WHILE
    // ведущие нули дробной части: значащих цифр у остатка меньше, чем знаков
    uliTmp := uliFrac;
    uiDigits := 0;
    WHILE uliTmp > 0 DO
        uliTmp := uliTmp / GVL_Const.DECIMAL_BASE;
        uiDigits := uiDigits + 1;
    END_WHILE
    WHILE uiDigits < uiFracDigits DO
        AppendByte(bChar := GVL_Const.ASCII_ZERO);
        uiDigits := uiDigits + 1;
    END_WHILE
    AppendUlint(uliNumber := uliFrac);
END_IF
