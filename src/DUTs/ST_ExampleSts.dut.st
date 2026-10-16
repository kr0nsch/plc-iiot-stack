// Назначение: состояние примера FB_Example для HMI/SCADA.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/ARCHITECTURE.md, раздел «Пример в src/»
TYPE ST_ExampleSts :
STRUCT
    eMode : E_DeviceMode;           // действующий режим
    xOut : BOOL;                    // выход включён
    xFault : BOOL;                  // отказ измерения зафиксирован, ждёт квитирования
    rSetpointUsed_pct : REAL;       // действующая уставка после ограничения, %
    udiCount : UDINT;               // число включений выхода с последнего сброса
END_STRUCT
END_TYPE
