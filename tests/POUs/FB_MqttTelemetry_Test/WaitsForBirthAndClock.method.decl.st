// До рождения узла и без часов ПЛК — ничего; потом — всё.
METHOD PRIVATE WaitsForBirthAndClock
VAR_INST
    fbFake : FB_MqttClientFake;
    fbTel : FB_MqttTelemetry;
    aPts : ARRAY[1..4] OF ST_IiotPoint;
END_VAR
