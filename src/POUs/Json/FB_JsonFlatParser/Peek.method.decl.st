// Текущий байт входа; за концом — 0.
METHOD PRIVATE Peek : BYTE
VAR_IN_OUT CONSTANT
    // lint:allow STL007 параметр VAR_IN_OUT CONSTANT — ссылка только для чтения, а не константа
    sJson : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
