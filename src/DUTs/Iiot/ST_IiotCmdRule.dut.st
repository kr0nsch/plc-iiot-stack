// Назначение: строка белого списка команд (command_whitelist.csv).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_IiotCmdRule :
STRUCT
    sDevice : STRING(GVL_Const.IIOT_DEVICE_LEN);    // 'P101'
    eCommand : E_IiotCommand := E_IiotCommand.None;
    xRange : BOOL;                                  // у команды есть диапазон value
    rMin : REAL;
    rMax : REAL;
    diDev : DINT;                                   // номер устройства для FB_IiotKnsMap.DeviceCmdState
END_STRUCT
END_TYPE
