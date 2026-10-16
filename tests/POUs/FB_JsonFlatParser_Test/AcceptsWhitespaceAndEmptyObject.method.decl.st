// Пробелы, табуляции и переводы строк между токенами; пустой объект.
METHOD PRIVATE AcceptsWhitespaceAndEmptyObject
VAR_INST
    fbParser : FB_JsonFlatParser;
    sJsonIn : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
