// Целое JSON — без дробной части и порядка: 1792137621000 — да, 1.0 и 1e3 — нет.
METHOD PRIVATE TracksIntegerLiterals
VAR_INST
    fbParser : FB_JsonFlatParser;
    sJsonIn : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
VAR
    lrNum : LREAL;
END_VAR
