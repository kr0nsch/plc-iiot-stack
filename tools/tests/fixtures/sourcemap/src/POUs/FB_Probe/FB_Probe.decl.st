FUNCTION_BLOCK FB_Probe IMPLEMENTS I_Prio
VAR
    afbT : ARRAY[0..GVL_Const.SLOTS_MAX - 1] OF TON;
    aaiGrid : ARRAY[0..1] OF
        ARRAY[0..2] OF INT;
    astP : ARRAY[0..1] OF ST_Probe;   // @6
    iSlot : INT := 0;                 // @7
    rX : REAL := 0.0;
    xQ : BOOL := FALSE;
    tT : TIME := T#0S;
    iPrio : INT := 0;
    wMask : WORD := WORD#16#FF;       // @12
END_VAR
