// Назначение: проверка, что REAL — конечное число (не NaN и не бесконечность): порядок не из одних единиц.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Построение JSON»
FUNCTION F_IsFiniteReal : BOOL
VAR_INPUT
    rValue : REAL;
END_VAR
VAR
    pBits : POINTER TO DWORD;   // те же 4 байта, что rValue
END_VAR
