// Назначение: тревога перечня флагмана (scada_alarms.csv, station_alarms.csv): номер, источник, суффикс,
//             бит в словах тревог, приоритет.
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_IiotAlarmCfg :
STRUCT
    udiId : UDINT;                                   // устройство: dev_no * 10 + слот; станция: 100000 + slot
    sDevice : STRING(GVL_Const.IIOT_DEVICE_LEN);     // 'P101', 'KNS1'
    sSuffix : STRING(GVL_Const.IIOT_SUFFIX_LEN);     // 'FTS'; код тревоги — <sDevice>.<sSuffix>
    uiSlot : UINT;                                   // бит в словах тревог (у станции slot - 1)
    ePriority : E_IiotAlarmPriority := E_IiotAlarmPriority.Medium;
    diWords : DINT;                                  // строка таблицы слов устройства (ST_IiotAlarmWords)
END_STRUCT
END_TYPE
