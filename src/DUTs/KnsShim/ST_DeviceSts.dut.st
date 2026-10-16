// Назначение: общий заголовок состояния устройства (28 байт, 14 регистров).
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
TYPE ST_DeviceSts :
STRUCT
    wStatus : WORD;
    wFault : WORD;
    wWarning : WORD;
    wCfgErr : WORD;
    eMode : E_DeviceMode := E_DeviceMode.Manual;
    eNe107 : E_Ne107Status := E_Ne107Status.CheckFunction;
    eCmdResult : E_CmdResult := E_CmdResult.None;
    uiCmdSeq : UINT;
    wAlmActive : WORD;
    wAlmUnack : WORD;
    wAlmShelved : WORD;
    ePrioUnack : E_AlarmPriority := E_AlarmPriority.None;
    eDevType : E_DeviceType := E_DeviceType.None;
    wReserve : WORD;
END_STRUCT
END_TYPE
