// Назначение: тип значения поля разобранного объекта JSON.
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_JsonType :
(
    Missing := 0,   // поля нет
    Text := 1,   // строка
    Number := 2,   // число
    Boolean := 3,   // true или false
    NullValue := 4   // null
) INT;
END_TYPE
