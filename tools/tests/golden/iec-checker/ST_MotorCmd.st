// Команды двигателя от HMI/SCADA
TYPE ST_MotorCmd :
STRUCT
    xStart : BOOL;                                  // пуск
    xStop : BOOL;                                   // стоп
    xAck : BOOL;                                    // квитирование
    eMode : E_DeviceMode;      // заданный режим
    rSpeedSp_rpm : REAL;                            // уставка скорости
END_STRUCT
END_TYPE
