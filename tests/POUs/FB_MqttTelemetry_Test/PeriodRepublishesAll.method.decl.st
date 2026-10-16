// По истечении периода — все метрики, раньше — нет.
METHOD PRIVATE PeriodRepublishesAll
VAR_INST
    fbFake : FB_MqttClientFake;
    fbTel : FB_MqttTelemetry;
    aPts : ARRAY[1..4] OF ST_IiotPoint;
END_VAR
