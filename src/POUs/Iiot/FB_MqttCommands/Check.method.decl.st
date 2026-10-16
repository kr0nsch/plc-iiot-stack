// Проверки шлюза по порядку data_schema 5.1, пункты 1–9; Ok — stCmd заполнена, момент учтён в частоте.
METHOD PRIVATE Check : E_IiotCmdReason
VAR_IN_OUT
    aRuleTable : ARRAY[*] OF ST_IiotCmdRule;
END_VAR
VAR
    sText : STRING(GVL_Const.JSON_STR_LEN);
    sKey : STRING(GVL_Const.JSON_KEY_LEN);
    iMajor : INT;
    uiIdx : UINT;
    lrTs : LREAL;
    lrValue : LREAL;
    lrMin : LREAL;
    lrMax : LREAL;
    xHasValue : BOOL;
    eCommand : E_IiotCommand;
    eKind : E_IiotCmdKind;
    diRule : DINT;
END_VAR
