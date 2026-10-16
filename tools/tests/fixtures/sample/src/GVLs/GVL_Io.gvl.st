// Сигналы ввода-вывода (привязка к каналам — в дереве устройств, docs/MANUAL_STEPS.md)
VAR_GLOBAL
    xMotorFeedback : BOOL;      // обратная связь контактора
    xMotorRun : BOOL;           // команда на контактор
    stMotorCmd : ST_MotorCmd;   // команды HMI
    stMotorSts : ST_MotorSts;   // состояние для HMI
    uRaw : U_RawValue;          // сырое значение Modbus
END_VAR
