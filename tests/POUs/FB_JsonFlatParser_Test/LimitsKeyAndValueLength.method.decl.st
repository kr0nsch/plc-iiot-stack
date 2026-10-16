// Ключ до 31 и строка до 64 символов; длиннее — KeyTooLong, ValueTooLong.
METHOD PRIVATE LimitsKeyAndValueLength
VAR_INST
    fbParser : FB_JsonFlatParser;
    sJsonIn : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
