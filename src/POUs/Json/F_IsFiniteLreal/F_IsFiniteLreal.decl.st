// Назначение: проверка, что LREAL — конечное число (не NaN и не бесконечность): порядок не из одних единиц.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Построение JSON»
FUNCTION F_IsFiniteLreal : BOOL
VAR_INPUT
    lrValue : LREAL;
END_VAR
VAR
    pBits : POINTER TO LWORD;   // те же 8 байт, что lrValue
END_VAR
