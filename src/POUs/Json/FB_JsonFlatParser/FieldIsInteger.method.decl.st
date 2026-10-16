// Поле sKey — число, записанное без дробной части и порядка (целое JSON Schema в строгом смысле).
METHOD FieldIsInteger : BOOL
VAR_INPUT
    sKey : STRING(GVL_Const.JSON_KEY_LEN);
END_VAR
VAR
    uiIdx : UINT;
END_VAR
