// Вложенный объект и массив — Nested.
METHOD PRIVATE RejectsNestedObjectsAndArrays
VAR_INST
    fbParser : FB_JsonFlatParser;
    sJsonIn : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
