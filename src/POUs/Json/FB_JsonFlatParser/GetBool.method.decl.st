// Логическое значение поля sKey. TRUE — поле есть и это true или false; иначе xValue не меняется.
METHOD GetBool : BOOL
VAR_INPUT
    sKey : STRING(GVL_Const.JSON_KEY_LEN);
END_VAR
VAR_IN_OUT
    xValue : BOOL;
END_VAR
VAR
    uiIdx : UINT;
END_VAR
