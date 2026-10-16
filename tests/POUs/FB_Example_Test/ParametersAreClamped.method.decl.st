// Уставка и гистерезис вне допустимых диапазонов ограничиваются границами из GVL_Const.
METHOD PRIVATE ParametersAreClamped
VAR
    fbDut : FB_Example;         // проверяемый экземпляр, новый при каждом вызове метода
END_VAR
