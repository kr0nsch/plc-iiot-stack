// Не своя станция, не JSON, нет или неверный cmd_id, обрезано — без ответа.
METHOD PRIVATE DropsWithoutAckWhenNoCmdId
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
