// Устройство с режимами работы
INTERFACE I_Device EXTENDS I_Resettable
METHOD Start
VAR_INPUT
    rSpeed_rpm : REAL;  // уставка скорости
END_VAR
END_METHOD
PROPERTY_GET Mode : E_DeviceMode
END_PROPERTY
PROPERTY_SET Mode : E_DeviceMode
END_PROPERTY
END_INTERFACE
