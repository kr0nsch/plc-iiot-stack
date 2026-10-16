// Escape-последовательности JSON; код вне ASCII и неизвестные — BadEscape.
METHOD PRIVATE DecodesEscapes
VAR_INST
    fbParser : FB_JsonFlatParser;
    sJsonIn : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
VAR
    sText : STRING(GVL_Const.JSON_STR_LEN);
END_VAR
