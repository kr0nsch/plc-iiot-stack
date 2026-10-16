// Три тревоги: P101.FTS (слот 0, Medium) и P101.FTP (слот 2, High) — слова 1; LT101.HH (слот 0, High) — слова 2.
METHOD PRIVATE Setup
VAR_IN_OUT
    fbClient : FB_MqttClientFake;
    aAlarmTable : ARRAY[1..3] OF ST_IiotAlarm;
END_VAR
