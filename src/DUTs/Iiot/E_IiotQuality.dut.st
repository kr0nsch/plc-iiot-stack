// Назначение: качество значения телеметрии (поле quality, data_schema 3.2).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_IiotQuality :
(
    Good := 0,   // 'good': Good или MaintenanceRequired, значение достоверно
    Uncertain := 1,   // 'uncertain': CheckFunction или OutOfSpecification
    Bad := 2   // 'bad': Failure, недостоверное значение, нет связи с ПЧ
) INT;
END_TYPE
