// Состояние двигателя: общее состояние устройства плюс данные привода
TYPE ST_MotorSts EXTENDS ST_DeviceSts :
STRUCT
    xRunning : BOOL;
    rSpeed_rpm : REAL;
    aLastFaults : ARRAY[1..3] OF E_NamurStatus;    // последние отказы
    wsText : WSTRING(80);                           // текст состояния для HMI
END_STRUCT
END_TYPE
