// Назначение: поле разобранного плоского объекта JSON.
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_JsonField :
STRUCT
    sKey : STRING(GVL_Const.JSON_KEY_LEN);
    eType : E_JsonType := E_JsonType.Missing;
    sText : STRING(GVL_Const.JSON_STR_LEN);   // eType = Text
    lrNumber : LREAL;                         // eType = Number
    xInteger : BOOL;                          // число записано без дробной части и порядка
    xBool : BOOL;                             // eType = Boolean
END_STRUCT
END_TYPE
