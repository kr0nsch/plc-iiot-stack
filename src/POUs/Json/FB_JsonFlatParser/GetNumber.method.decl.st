// Числовое значение поля sKey. TRUE — поле есть и это число; иначе lrValue не меняется.
METHOD GetNumber : BOOL
VAR_INPUT
    sKey : STRING(GVL_Const.JSON_KEY_LEN);
END_VAR
VAR_IN_OUT
    lrValue : LREAL;
END_VAR
VAR
    uiIdx : UINT;
END_VAR
