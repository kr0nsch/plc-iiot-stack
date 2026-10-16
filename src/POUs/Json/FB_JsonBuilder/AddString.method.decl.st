// Поле со строковым значением; кавычки, обратная косая черта и управляющие символы экранируются.
METHOD AddString
VAR_INPUT
    sKey : STRING(GVL_Const.JSON_KEY_LEN);
    sValue : STRING(GVL_Const.JSON_STR_LEN);
END_VAR
