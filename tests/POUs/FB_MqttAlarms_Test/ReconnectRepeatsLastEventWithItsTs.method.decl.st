// Тревога сработала, связь пропала и вернулась: событие Activated повторяется с исходными ts и prev_state
// (в InfluxDB та же точка) — дашборды и отчёт не считают его вторым срабатыванием.
METHOD PRIVATE ReconnectRepeatsLastEventWithItsTs
VAR_INST
    fbFake : FB_MqttClientFake;
    fbAlm : FB_MqttAlarms;
    aAlm : ARRAY[1..3] OF ST_IiotAlarm;
    aWords : ARRAY[1..2] OF ST_IiotAlarmWords;
END_VAR
