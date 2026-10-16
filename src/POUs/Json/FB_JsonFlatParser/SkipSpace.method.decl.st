// Пропустить пробельные символы JSON: пробел, табуляция, перевод строки, возврат каретки.
METHOD PRIVATE SkipSpace
VAR_IN_OUT CONSTANT
    // lint:allow STL007 параметр VAR_IN_OUT CONSTANT — ссылка только для чтения, а не константа
    sJson : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
VAR
    bCh : BYTE;
END_VAR
