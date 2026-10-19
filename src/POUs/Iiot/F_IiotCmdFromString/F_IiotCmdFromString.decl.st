// Назначение: команда по имени поля command (с учётом регистра, enum command.schema.json);
//             неизвестное имя — None.
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Команды»
FUNCTION F_IiotCmdFromString : E_IiotCommand
VAR_INPUT
    sCommand : STRING(GVL_Const.JSON_STR_LEN);
END_VAR
