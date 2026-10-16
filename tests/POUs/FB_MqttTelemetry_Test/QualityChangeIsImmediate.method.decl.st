// Смена качества публикуется сразу, без ожидания интервала.
METHOD PRIVATE QualityChangeIsImmediate
VAR_INST
    fbFake : FB_MqttClientFake;
    fbTel : FB_MqttTelemetry;
    aPts : ARRAY[1..4] OF ST_IiotPoint;
END_VAR
