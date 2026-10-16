// Пустой вход, не объект, незакрытый объект, нет двоеточия, лишняя запятая, ключ без кавычек.
METHOD PRIVATE RejectsSyntaxErrors
VAR_INST
    fbParser : FB_JsonFlatParser;
    sJsonIn : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
