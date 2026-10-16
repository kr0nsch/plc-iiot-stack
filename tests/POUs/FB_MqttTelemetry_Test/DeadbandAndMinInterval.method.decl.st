// Зона нечувствительности и не чаще раза в секунду на метрику.
METHOD PRIVATE DeadbandAndMinInterval
VAR_INST
    fbFake : FB_MqttClientFake;
    fbTel : FB_MqttTelemetry;
    aPts : ARRAY[1..4] OF ST_IiotPoint;
END_VAR
