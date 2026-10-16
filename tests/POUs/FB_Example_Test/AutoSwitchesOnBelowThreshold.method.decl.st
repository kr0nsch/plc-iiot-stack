// Авторежим: значение ниже порога включения (уставка - гистерезис) включает выход.
METHOD PRIVATE AutoSwitchesOnBelowThreshold
VAR
    fbDut : FB_Example;         // проверяемый экземпляр, новый при каждом вызове метода
END_VAR
