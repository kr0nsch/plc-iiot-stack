// Назначение: вид команды по полю value (command.schema.json).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_IiotCmdKind :
(
    Pulse := 0,   // импульс: поля value быть не должно
    Value := 1,   // значение: value обязательно (SpeedSp, SubstValue)
    Mask := 2   // маска: value — целое 0..65535 (AckReq, ShelveReq, UnshelveReq)
) INT;
END_TYPE
