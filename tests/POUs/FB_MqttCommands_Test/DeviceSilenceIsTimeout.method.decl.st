// Устройство не обработало команду за 3 с — timeout; новое сообщение ждёт.
METHOD PRIVATE DeviceSilenceIsTimeout
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
