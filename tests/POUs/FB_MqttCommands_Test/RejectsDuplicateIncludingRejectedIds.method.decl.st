// Повтор cmd_id среди последних 16 (и отклонённых тоже) — duplicate.
METHOD PRIVATE RejectsDuplicateIncludingRejectedIds
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
