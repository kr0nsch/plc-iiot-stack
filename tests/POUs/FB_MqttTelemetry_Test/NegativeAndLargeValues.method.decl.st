// Отрицательное Analog и большой счётчик Integer — без потери знака и разрядов.
METHOD PRIVATE NegativeAndLargeValues
VAR_INST
    fbFake : FB_MqttClientFake;
    fbTel : FB_MqttTelemetry;
    aPts : ARRAY[1..4] OF ST_IiotPoint;
END_VAR
