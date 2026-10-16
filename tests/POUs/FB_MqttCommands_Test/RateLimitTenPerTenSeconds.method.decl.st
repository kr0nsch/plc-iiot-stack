// Не больше 10 команд за 10 с — rate_limited; после окна — снова принимаются.
METHOD PRIVATE RateLimitTenPerTenSeconds
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
