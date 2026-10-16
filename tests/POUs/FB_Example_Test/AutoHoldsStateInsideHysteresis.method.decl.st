// Авторежим: внутри зоны гистерезиса выход сохраняет прежнее состояние в обе стороны.
METHOD PRIVATE AutoHoldsStateInsideHysteresis
VAR
    fbDut : FB_Example;         // проверяемый экземпляр, новый при каждом вызове метода
END_VAR
