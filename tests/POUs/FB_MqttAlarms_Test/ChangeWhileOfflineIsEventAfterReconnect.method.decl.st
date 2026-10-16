// Тревога сработала, пока связи не было: после переподключения — событие с текущим ts и prev_state
// последней публикации.
METHOD PRIVATE ChangeWhileOfflineIsEventAfterReconnect
VAR_INST
    fbFake : FB_MqttClientFake;
    fbAlm : FB_MqttAlarms;
    aAlm : ARRAY[1..3] OF ST_IiotAlarm;
    aWords : ARRAY[1..2] OF ST_IiotAlarmWords;
END_VAR
