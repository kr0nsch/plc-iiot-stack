// После рождения узла — все метрики; точный JSON, QoS 1, retain.
METHOD PRIVATE PublishesAllAfterBirthWithExactJson
VAR_INST
    fbFake : FB_MqttClientFake;
    fbTel : FB_MqttTelemetry;
    aPts : ARRAY[1..4] OF ST_IiotPoint;
END_VAR
