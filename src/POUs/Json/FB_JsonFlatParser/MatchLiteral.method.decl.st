// Сравнить вход с литералом (true, false, null) и сдвинуть позицию за него. FALSE — ошибка Syntax.
METHOD PRIVATE MatchLiteral : BOOL
VAR_IN_OUT CONSTANT
    // lint:allow STL007 параметр VAR_IN_OUT CONSTANT — ссылка только для чтения, а не константа
    sJson : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
VAR_INPUT
    sLiteral : STRING(GVL_Const.JSON_LITERAL_LEN);
END_VAR
VAR
    uiLitLen : UINT;
    uiIdx : UINT;
END_VAR
