// Назначение: имя состояния тревоги для полей state и prev_state.
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Тревоги»
FUNCTION F_IiotAlarmStateText : STRING(GVL_Const.IIOT_TEXT_LEN)
VAR_INPUT
    eState : E_IiotAlarmState;
END_VAR
