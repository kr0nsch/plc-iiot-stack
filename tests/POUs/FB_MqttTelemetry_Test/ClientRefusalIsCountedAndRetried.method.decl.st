// Клиент не принял — udiFailed, метрики ждут и уходят позже.
METHOD PRIVATE ClientRefusalIsCountedAndRetried
VAR_INST
    fbFake : FB_MqttClientFake;
    fbTel : FB_MqttTelemetry;
    aPts : ARRAY[1..4] OF ST_IiotPoint;
END_VAR
