// Поле с числом: uiDecimals знаков после точки (не больше JSON_REAL_DECIMALS_MAX), хвостовые нули
// отбрасываются; NaN, бесконечность и слишком большие числа — null. REAL приводится к LREAL.
METHOD AddReal
VAR_INPUT
    sKey : STRING(GVL_Const.JSON_KEY_LEN);
    lrValue : LREAL;
    uiDecimals : UINT;
END_VAR
