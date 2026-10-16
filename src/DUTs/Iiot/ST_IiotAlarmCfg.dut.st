// Назначение: тревога перечня флагмана (scada_alarms.csv): номер, устройство, суффикс, слот, приоритет.
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_IiotAlarmCfg :
STRUCT
    uiId : UINT;                                     // udiId = dev_no * 10 + слот
    sDevice : STRING(GVL_Const.IIOT_DEVICE_LEN);     // 'P101'
    sSuffix : STRING(GVL_Const.IIOT_SUFFIX_LEN);     // 'FTS'; код тревоги — <sDevice>.<sSuffix>
    uiSlot : UINT;                                   // бит в словах wAlmActive, wAlmUnack, wAlmShelved
    ePriority : E_IiotAlarmPriority := E_IiotAlarmPriority.Medium;
    diWords : DINT;                                  // строка таблицы слов устройства (ST_IiotAlarmWords)
END_STRUCT
END_TYPE
