// После неудачного разбора поля прошлого объекта не видны.
METHOD PRIVATE FailedParseClearsPreviousFields
VAR_INST
    fbParser : FB_JsonFlatParser;
    sJsonIn : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
