// Команда с флагом retain — retained.
METHOD PRIVATE RejectsRetainedCommand
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
