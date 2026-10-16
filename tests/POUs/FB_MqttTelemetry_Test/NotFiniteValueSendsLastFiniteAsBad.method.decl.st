// Значение стало NaN: схема требует число — передаётся последнее опубликованное конечное значение с
// quality = bad; конечное значение возвращает исходное качество.
METHOD PRIVATE NotFiniteValueSendsLastFiniteAsBad
VAR_INST
    fbFake : FB_MqttClientFake;
    fbTel : FB_MqttTelemetry;
    aPts : ARRAY[1..4] OF ST_IiotPoint;
END_VAR
VAR
    lwNan : LWORD := 16#7FF8000000000000;
    pBits : POINTER TO LREAL;
END_VAR
