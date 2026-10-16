// Start прошёл шлюз: stCmd, ответа нет до обработки устройством, затем ok.
METHOD PRIVATE AcceptedStartWaitsForDeviceThenOk
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
