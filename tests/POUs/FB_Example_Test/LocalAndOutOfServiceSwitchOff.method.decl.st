// Режимы Local и OutOfService снимают команду ПЛК при любом измерении и команде.
METHOD PRIVATE LocalAndOutOfServiceSwitchOff
VAR
    fbDut : FB_Example;         // проверяемый экземпляр, новый при каждом вызове метода
END_VAR
