// Бит wAlmSuppressed устройства (plc-process-lib 1.0) — состояние SuppressedByDesign и причины Suppressed/Unsuppressed.
METHOD PRIVATE SuppressedByDesignFromWords
VAR_INST
    fbFake : FB_MqttClientFake;
    fbAlm : FB_MqttAlarms;
    aAlm : ARRAY[1..3] OF ST_IiotAlarm;
    aWords : ARRAY[1..2] OF ST_IiotAlarmWords;
END_VAR
