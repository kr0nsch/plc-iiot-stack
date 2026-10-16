// Назначение: вид значения метрики в JSON.
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_IiotValueKind :
(
    Analog := 0,   // число с дробной частью: analog и накопительные REAL (наработка)
    Integer := 1   // целое: discrete (0/1), enum (код), counter, integer
) INT;
END_TYPE
