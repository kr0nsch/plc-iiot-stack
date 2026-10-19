// Назначение: для тестов — содержит ли текст длиной до MQTT_PAYLOAD_LEN подстроку sPart (стандартная
//             FIND работает только со строками до 255 символов).
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/TEST_REPORT.md
FUNCTION F_TestContains : BOOL
VAR_IN_OUT CONSTANT
    // lint:allow STL007 параметр VAR_IN_OUT CONSTANT — ссылка только для чтения, а не константа
    sText : STRING(GVL_Const.MQTT_PAYLOAD_LEN);
END_VAR
VAR_INPUT
    sPart : STRING(255);
END_VAR
VAR
    uiTextLen : UINT;
    uiPartLen : UINT;
    uiStart : UINT;
    uiIdx : UINT;
    xMatch : BOOL;
END_VAR
