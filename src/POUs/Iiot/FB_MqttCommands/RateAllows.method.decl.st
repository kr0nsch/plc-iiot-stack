// Частота: не больше uiRateLimit прошедших команд за tRateWindow. TRUE — команда разрешена и учтена.
METHOD PRIVATE RateAllows : BOOL
VAR
    uiLimit : UINT;
END_VAR
