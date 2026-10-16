// Назначение: метрика каталога: топик <prefix>/<sPath>, вид, единица, зона нечувствительности.
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_IiotPointCfg :
STRUCT
    sPath : STRING(GVL_Const.IIOT_PATH_LEN);        // device/metric, например 'LT101/level'
    sUnit : STRING(GVL_Const.IIOT_UNIT_LEN);        // единица (ASCII); пусто — поля unit нет
    eKind : E_IiotValueKind := E_IiotValueKind.Integer;
    rDeadband : REAL;                               // зона нечувствительности, ед.; 0 — любое изменение
    uiDecimals : UINT := GVL_Const.JSON_REAL_DECIMALS_DEFAULT;   // знаков после точки (Analog)
    xPeriodicOnly : BOOL;                           // только с контрольной публикацией (uptime)
END_STRUCT
END_TYPE
