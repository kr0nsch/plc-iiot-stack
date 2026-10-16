// Назначение: причина события по переходу состояний ePrev -> eNew. ePrev = eNew — снимок после
//             подключения: причина, которая привела бы в это состояние (Normal — Cleared).
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Тревоги»
FUNCTION F_IiotAlarmReason : E_IiotAlarmReason
VAR_INPUT
    ePrev : E_IiotAlarmState;
    eNew : E_IiotAlarmState;
END_VAR
