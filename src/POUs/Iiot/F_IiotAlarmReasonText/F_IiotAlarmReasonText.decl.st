// Назначение: имя причины события тревоги для поля reason.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Тревоги»
FUNCTION F_IiotAlarmReasonText : STRING(GVL_Const.IIOT_TEXT_LEN)
VAR_INPUT
    eReason : E_IiotAlarmReason;
END_VAR
