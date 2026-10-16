// Назначение: приоритет тревоги (коды PL.E_AlarmPriority).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_IiotAlarmPriority :
(
    None := 0,   // выключена
    Low := 1,   // 'Low'
    Medium := 2,   // 'Medium'
    High := 3,   // 'High'
    Critical := 4   // 'Critical'
) INT;
END_TYPE
