Check := TRUE;
FOR iIdx := 0 TO GVL_Const.SLOTS_MAX - 1 DO
    Check := Check AND astCfg[iIdx].rValue >= 0.0;
END_FOR
