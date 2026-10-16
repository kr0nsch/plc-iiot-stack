// NaN, бесконечность и слишком большие числа пишутся как null.
METHOD PRIVATE NotFiniteBecomesNull
VAR_INST
    fbJson : FB_JsonBuilder;
END_VAR
VAR
    lwNan : LWORD := 16#7FF8000000000000;
    lwInf : LWORD := 16#7FF0000000000000;
    pBits : POINTER TO LREAL;
    lrNan : LREAL;
    lrInf : LREAL;
END_VAR
