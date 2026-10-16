// Целые — при любом изменении; время работы узла — только контрольно.
METHOD PRIVATE IntegerAnyChangeAndPeriodicOnly
VAR_INST
    fbFake : FB_MqttClientFake;
    fbTel : FB_MqttTelemetry;
    aPts : ARRAY[1..4] OF ST_IiotPoint;
END_VAR
