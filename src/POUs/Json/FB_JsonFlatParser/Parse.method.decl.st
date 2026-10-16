// Разобрать объект. TRUE — разбор успешен (uiCount полей); FALSE — eError и uiErrorPos.
METHOD Parse : BOOL
VAR_IN_OUT CONSTANT
    // lint:allow STL007 параметр VAR_IN_OUT CONSTANT — ссылка только для чтения, а не константа
    sJson : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
VAR
    bCh : BYTE;
    stField : ST_JsonField;
END_VAR
