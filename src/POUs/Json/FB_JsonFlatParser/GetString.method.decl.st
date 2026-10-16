// Строковое значение поля sKey. TRUE — поле есть и это строка; иначе sValue не меняется.
METHOD GetString : BOOL
VAR_INPUT
    sKey : STRING(GVL_Const.JSON_KEY_LEN);
END_VAR
VAR_IN_OUT
    sValue : STRING(GVL_Const.JSON_STR_LEN);
END_VAR
VAR
    uiIdx : UINT;
END_VAR
