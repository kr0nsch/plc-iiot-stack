uliRest := uliNumber;
uiCount := 0;
REPEAT
    aDigits[uiCount] := GVL_Const.ASCII_ZERO + ULINT_TO_BYTE(uliRest MOD GVL_Const.DECIMAL_BASE);
    uliRest := uliRest / GVL_Const.DECIMAL_BASE;
    uiCount := uiCount + 1;
UNTIL uliRest = 0 OR uiCount >= GVL_Const.ULINT_DIGITS_MAX
END_REPEAT
WHILE uiCount > 0 DO
    uiCount := uiCount - 1;
    AppendByte(bChar := aDigits[uiCount]);
END_WHILE
