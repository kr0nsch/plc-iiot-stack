// SpeedSp: ok сразу после записи (ФБ устройства значения не квитирует); границы 0 и 100.
METHOD PRIVATE SpeedSetpointIsOkAfterWrite
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
