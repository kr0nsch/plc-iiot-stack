// Полей не больше 12; 13-е — TooManyFields.
METHOD PRIVATE LimitsFieldCount
VAR_INST
    fbParser : FB_JsonFlatParser;
    sJsonIn : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
