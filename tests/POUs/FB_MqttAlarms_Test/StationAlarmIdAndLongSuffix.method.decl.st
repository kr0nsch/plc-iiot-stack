// Тревога станции флагмана KNS1.NOAUTO: номер 100009 (больше UINT), суффикс из шести знаков, бит slot - 1.
METHOD PRIVATE StationAlarmIdAndLongSuffix
VAR_INST
    fbFake : FB_MqttClientFake;
    fbAlm : FB_MqttAlarms;
    aAlm : ARRAY[1..1] OF ST_IiotAlarm;
    aWords : ARRAY[1..1] OF ST_IiotAlarmWords;
END_VAR
