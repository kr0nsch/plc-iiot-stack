// SpeedSp вне 0..100 % — out_of_range.
METHOD PRIVATE RejectsOutOfRange
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
