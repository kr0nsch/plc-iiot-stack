// Устройство отказало — device_rejected и cmd_result по E_CmdResult.
METHOD PRIVATE DeviceRejectedCarriesCmdResult
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
