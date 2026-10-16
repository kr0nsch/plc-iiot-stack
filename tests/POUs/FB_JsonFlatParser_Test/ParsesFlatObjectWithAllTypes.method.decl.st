// Строка, число с порядком, true, false, null; поиск по ключу, ключ по номеру.
METHOD PRIVATE ParsesFlatObjectWithAllTypes
VAR_INST
    fbParser : FB_JsonFlatParser;
    sJsonIn : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
VAR
    sText : STRING(GVL_Const.JSON_STR_LEN);
    lrNum : LREAL;
    xFlag : BOOL;
END_VAR
