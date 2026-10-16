// Общее состояние устройства для HMI/SCADA
TYPE ST_DeviceSts :
STRUCT
    eMode : E_DeviceMode;
    eNamur : E_NamurStatus;
    xFault : BOOL;
END_STRUCT
END_TYPE
