// Счётчик считает включения по фронту выхода; Reset() через I_Resettable отключает
// выход и обнуляет счётчик.
METHOD PRIVATE CountsSwitchOnsAndResetClears
VAR
    fbDut : FB_Example;         // проверяемый экземпляр, новый при каждом вызове метода
    itfDut : I_Resettable;      // сброс через интерфейс, как в PRG_Main
    xResetResult : BOOL;        // результат Reset()
END_VAR
