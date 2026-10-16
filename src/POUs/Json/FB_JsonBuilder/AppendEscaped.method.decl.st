// Дописать строку с экранированием JSON: \" \\ \n \r \t \b \f; прочие управляющие символы и байты
// не из ASCII — \u00XX (байт как символ Latin-1; строки ПЛК в этом проекте — ASCII).
METHOD PRIVATE AppendEscaped
VAR_INPUT
    sText : STRING(GVL_Const.JSON_STR_LEN);
END_VAR
VAR
    uiTextLen : UINT;
    uiIdx : UINT;
    bCh : BYTE;
END_VAR
