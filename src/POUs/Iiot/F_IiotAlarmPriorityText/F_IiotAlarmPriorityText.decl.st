// Назначение: имя приоритета тревоги для поля priority (None — пусто: тревога не
//             публикуется).
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Тревоги»
FUNCTION F_IiotAlarmPriorityText : STRING(GVL_Const.IIOT_TEXT_LEN)
VAR_INPUT
    ePriority : E_IiotAlarmPriority;
END_VAR
