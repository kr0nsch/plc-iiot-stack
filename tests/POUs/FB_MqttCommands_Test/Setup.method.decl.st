// Белый список: P101 Start, SpeedSp (0..100 %), Ack; LT101 Ack. Связь есть.
METHOD PRIVATE Setup
VAR_IN_OUT
    fbClient : FB_MqttClientFake;
    aRuleTable : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
