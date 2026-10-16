// Назначение: вид команды по полю value: значение (SpeedSp, SubstValue), маска (AckReq,
//             ShelveReq, UnshelveReq) или импульс (остальные).
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Команды»
FUNCTION F_IiotCmdKind : E_IiotCmdKind
VAR_INPUT
    eCommand : E_IiotCommand;
END_VAR
