// Назначение: качество метрики по статусу NE 107 и достоверности устройства (data_schema 3.2):
//             F — bad; S, C — uncertain; Good, M — good при достоверном значении, иначе bad.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Телеметрия»
FUNCTION F_IiotQuality : E_IiotQuality
VAR_INPUT
    xValid : BOOL;   // значение достоверно (выход xValid AI и DI; для двигателя — TRUE)
    iNe107 : INT;    // код E_Ne107Status устройства (0 Good ... 4 Failure)
END_VAR
