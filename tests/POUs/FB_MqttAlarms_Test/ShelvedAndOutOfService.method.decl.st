// Отложена/возвращена и вывод устройства из работы: Shelved, Unshelved, OosOn.
METHOD PRIVATE ShelvedAndOutOfService
VAR_INST
    fbFake : FB_MqttClientFake;
    fbAlm : FB_MqttAlarms;
    aAlm : ARRAY[1..3] OF ST_IiotAlarm;
    aWords : ARRAY[1..2] OF ST_IiotAlarmWords;
END_VAR
