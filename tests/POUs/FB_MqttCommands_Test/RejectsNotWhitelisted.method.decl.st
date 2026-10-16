// Пары (устройство, команда) нет в белом списке — not_whitelisted.
METHOD PRIVATE RejectsNotWhitelisted
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
