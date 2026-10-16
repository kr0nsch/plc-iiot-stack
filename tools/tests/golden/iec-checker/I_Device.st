// Устройство с режимами работы
INTERFACE I_Device EXTENDS I_Resettable
METHOD Start
VAR_INPUT
    rSpeed_rpm : REAL;  // уставка скорости
END_VAR
END_METHOD
METHOD Mode__get : E_DeviceMode
END_METHOD
METHOD Mode__set
VAR_INPUT
    Mode : E_DeviceMode;
END_VAR
END_METHOD
END_INTERFACE
