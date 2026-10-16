// Назначение: построитель плоского объекта JSON в буфере STRING(GVL_Const.MQTT_PAYLOAD_LEN) побайтно, без
//             CONCAT (стандартные строковые функции ограничены 255 символами). Ключи и строки
//             экранируются, REAL — с фиксированным числом знаков без хвостовых нулей, NaN и
//             бесконечность — null, целые — LINT. Переполнение буфера фиксируется флагом xOverflow:
//             неполный JSON публиковать нельзя.
//             Порядок: Begin(), Add...() для каждого поля, Finish() (TRUE — объект закончен и помещается).
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Построение JSON»
FUNCTION_BLOCK FB_JsonBuilder
VAR_OUTPUT
    sJson : STRING(GVL_Const.MQTT_PAYLOAD_LEN);   // текст JSON
    uiLen : UINT;                                  // длина текста, байт
    xOverflow : BOOL;                              // буфер переполнен: текст неполный
END_VAR
VAR
    xNeedComma : BOOL;                             // перед следующим полем нужна запятая
END_VAR
