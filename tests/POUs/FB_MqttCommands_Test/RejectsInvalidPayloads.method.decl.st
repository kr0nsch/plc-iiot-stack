// Не по command.schema.json — invalid_payload: лишние поля, ts, origin, command, value.
METHOD PRIVATE RejectsInvalidPayloads
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
