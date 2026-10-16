IF rY = 1.5 THEN rY := 0.0; ELSE rY := 1.0; END_IF   // @1
rY := astP[iSlot].arStep[1]
    + astP[0].rLim;
IF rY = 1.5 THEN rY := 0.0; ELSE rY := 1.0; END_IF   // @4
WHILE FALSE DO
END_WHILE
IF rY = 1.5 THEN rY := 0.0; ELSE rY := 1.0; END_IF   // @7
Run := TRUE;
