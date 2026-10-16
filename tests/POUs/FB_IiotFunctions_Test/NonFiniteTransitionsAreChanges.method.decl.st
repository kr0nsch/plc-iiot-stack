// Переход между числом и NaN/бесконечностью — изменение; два неконечных — нет.
METHOD PRIVATE NonFiniteTransitionsAreChanges
VAR
    lwNan : LWORD := 16#7FF8000000000000;
    lwInf : LWORD := 16#7FF0000000000000;
    pBits : POINTER TO LREAL;
    lrNan : LREAL;
    lrInf : LREAL;
END_VAR
