// Назначение: слова тревог источника (stSts.stCommon устройства или stStationSts станции) и признак
//             вывода из работы.
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_IiotAlarmWords :
STRUCT
    wActive : WORD;          // wAlmActive
    wUnack : WORD;           // wAlmUnack
    wShelved : WORD;         // wAlmShelved: отложен оператором (у станции — и подавлен, и выведен)
    wSuppressed : WORD;      // wAlmSuppressed: подавлен логикой (SuppressedByDesign); у станции 0
    xOutOfService : BOOL;    // eMode = OutOfService
END_STRUCT
END_TYPE
