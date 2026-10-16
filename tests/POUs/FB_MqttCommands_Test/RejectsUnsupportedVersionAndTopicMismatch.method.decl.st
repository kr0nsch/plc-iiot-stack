// schema_version 2.0 — unsupported_version; команда не та, что в топике.
METHOD PRIVATE RejectsUnsupportedVersionAndTopicMismatch
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
