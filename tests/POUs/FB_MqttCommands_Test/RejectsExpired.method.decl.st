// ts дальше 30 с от часов ПЛК (в прошлое или будущее) или часов нет — expired.
METHOD PRIVATE RejectsExpired
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
