// Назначение: причина события тревоги (коды PL.E_AlarmEventReason).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_IiotAlarmReason :
(
    None := 0,   // нет
    Activated := 1,   // условие появилось
    Cleared := 2,   // условие ушло
    Acked := 3,   // квитирована
    Shelved := 4,   // отложена
    Unshelved := 5,   // возвращена командой
    ShelveExpired := 6,   // возвращена по таймауту
    Suppressed := 7,   // подавлена
    Unsuppressed := 8,   // подавление снято
    OosOn := 9,   // выведена из работы
    OosOff := 10   // введена в работу
) INT;
END_TYPE
