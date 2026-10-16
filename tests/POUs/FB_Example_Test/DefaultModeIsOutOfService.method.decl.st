// Пока режим не назначен (значение входа по умолчанию), выход отключён.
METHOD PRIVATE DefaultModeIsOutOfService
VAR
    fbDut : FB_Example;         // проверяемый экземпляр, новый при каждом вызове метода
END_VAR
