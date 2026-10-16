// Назначение: слова тревог устройства из stSts.stCommon и признак вывода из работы.
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_IiotAlarmWords :
STRUCT
    wActive : WORD;          // wAlmActive
    wUnack : WORD;           // wAlmUnack
    wShelved : WORD;         // wAlmShelved: Shelved, SuppressedByDesign или OutOfService
    xOutOfService : BOOL;    // eMode = OutOfService
END_STRUCT
END_TYPE
