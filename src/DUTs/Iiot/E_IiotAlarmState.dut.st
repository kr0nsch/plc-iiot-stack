// Назначение: состояние тревоги (коды PL.E_AlarmState).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_IiotAlarmState :
(
    Normal := 0,   // норма
    ActiveUnack := 1,   // активна, не квитирована
    ActiveAck := 2,   // активна, квитирована
    RtnUnack := 3,   // вернулась в норму без квитирования
    Shelved := 4,   // отложена
    SuppressedByDesign := 5,   // подавлена логикой
    OutOfService := 6   // выведена из работы с устройством
) INT;
END_TYPE
