// Назначение: команды двигателя.
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
TYPE ST_MotorCmd :
STRUCT
    stCommon : ST_DeviceCmd;
    xStart : BOOL;          // импульс: пуск (Manual)
    xStop : BOOL;           // импульс: стоп
    xResetMaint : BOOL;     // импульс: обнулить счётчики ТО
    rSpeedSp_pct : REAL;    // ПЧ: задание скорости в Manual, %
END_STRUCT
END_TYPE
