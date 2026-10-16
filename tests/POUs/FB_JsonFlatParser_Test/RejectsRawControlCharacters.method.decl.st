// Управляющий символ внутри строки без экранирования — Syntax.
METHOD PRIVATE RejectsRawControlCharacters
VAR_INST
    fbParser : FB_JsonFlatParser;
    sJsonIn : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
