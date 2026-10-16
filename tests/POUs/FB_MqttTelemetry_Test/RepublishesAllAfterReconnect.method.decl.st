// Связь пропала и вернулась с новым рождением — все метрики заново.
METHOD PRIVATE RepublishesAllAfterReconnect
VAR_INST
    fbFake : FB_MqttClientFake;
    fbTel : FB_MqttTelemetry;
    aPts : ARRAY[1..4] OF ST_IiotPoint;
END_VAR
