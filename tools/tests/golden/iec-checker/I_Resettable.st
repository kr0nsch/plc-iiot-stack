// Сброс отказа (квитирование)
INTERFACE I_Resettable
// Сброс; TRUE — отказ сброшен
METHOD Reset : BOOL
VAR_INPUT
    xForce : BOOL;  // сброс без проверки условий
END_VAR
END_METHOD
END_INTERFACE
