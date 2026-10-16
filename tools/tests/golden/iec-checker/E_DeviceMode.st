

// Режим работы устройства (docs/ARCHITECTURE.md, раздел «Режимы»)
TYPE E_DeviceMode :
(
    Auto := 0,          // автоматический
    Manual := 1,        // ручной с HMI
    Local := 2,         // местный пост
    OutOfService := 3   // выведен из работы
) ;
END_TYPE
