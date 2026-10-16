// Дописать число с uiDecimalsMax знаками (округление до ближайшего), без хвостовых нулей; -0 пишется как 0.
METHOD PRIVATE AppendReal
VAR_INPUT
    lrNumber : LREAL;
    uiDecimalsMax : UINT;
END_VAR
VAR
    uiDecimals : UINT;
    uiIdx : UINT;
    uliScale : ULINT;          // 10^uiDecimals
    lrScaled : LREAL;
    uliScaled : ULINT;
    uliFrac : ULINT;
    uiFracDigits : UINT;       // значащих знаков дробной части после отбрасывания нулей
    uiDigits : UINT;
    uliTmp : ULINT;
END_VAR
