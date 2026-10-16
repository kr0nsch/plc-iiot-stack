Reset := SUPER^.Reset(xForce := xForce);
IF itfInterlock <> 0 THEN
    itfInterlock.Reset(xForce := xForce);
END_IF
fbStartTimer(IN := FALSE);
iStep := GVL_Const.STEP_IDLE;
