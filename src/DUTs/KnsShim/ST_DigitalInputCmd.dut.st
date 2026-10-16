// Назначение: команды дискретного входа.
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
TYPE ST_DigitalInputCmd :
STRUCT
    stCommon : ST_DeviceCmd;
    xSubstValue : BOOL;
END_STRUCT
END_TYPE
