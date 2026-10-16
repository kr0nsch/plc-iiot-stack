// Авторежим: на пороге включения выход включается, на уставке — отключается.
METHOD PRIVATE AutoThresholdsAreInclusive
VAR
    fbDut : FB_Example;         // проверяемый экземпляр, новый при каждом вызове метода
END_VAR
