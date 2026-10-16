// Назначение: пример ФБ устройства — двухпозиционный регулятор с гистерезисом
//             (насос подкачки по уровню): включение при значении не выше
//             (уставка - гистерезис), отключение при значении не ниже уставки.
//             Режимы E_DeviceMode, безопасное состояние (выход отключён) при отказе
//             измерения, квитирование отказа, счётчик включений для оценки износа.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/ARCHITECTURE.md, раздел «Пример в src/»
FUNCTION_BLOCK FB_Example IMPLEMENTS I_Resettable
VAR_INPUT
    // режим работы; пока режим не назначен — выведено из работы
    eMode : E_DeviceMode := E_DeviceMode.OutOfService;
    rValue_pct : REAL;          // измеренное значение, % диапазона датчика
    xValueValid : BOOL;         // измерение достоверно (например, по NAMUR NE 43)
    rSetpoint_pct : REAL := GVL_Const.EXAMPLE_SP_DEFAULT_PCT;       // уставка отключения, %
    rHysteresis_pct : REAL := GVL_Const.EXAMPLE_HYST_DEFAULT_PCT;   // гистерезис ниже уставки, %
    xManualOn : BOOL;           // команда «включить» в ручном режиме
END_VAR
VAR_OUTPUT
    xOut : BOOL;                // TRUE — исполнительный механизм включён
    xFault : BOOL;              // отказ измерения зафиксирован, нужен вызов Acknowledge()
    rSetpointUsed_pct : REAL;   // уставка после ограничения диапазоном, %
    rHysteresisUsed_pct : REAL; // гистерезис после ограничения диапазоном, %
END_VAR
VAR
    xOutPrev : BOOL;            // выход в предыдущем вызове — для счёта включений по фронту
    udiCount : UDINT;           // число включений выхода с последнего Reset()
END_VAR
