// Назначение: сводный статус связи в духе NAMUR NE 107 (те же коды, что PL.E_Ne107Status флагмана).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_IiotNe107 :
(
    Good := 0,   // норма: связь есть, публикации проходят
    MaintenanceRequired := 1,   // M: связь есть, но публикации отклоняются (очередь клиента)
    OutOfSpecification := 2,   // S: связь потеряна или не установлена, идут повторы
    CheckFunction := 3,   // C: обмен выключен, нет часов или первое подключение
    Failure := 4   // F: подряд неудачных подключений не меньше порога
) INT;
END_TYPE
