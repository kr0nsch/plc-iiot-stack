FOR diIdx := LOWER_BOUND(aPointTable, 1) TO UPPER_BOUND(aPointTable, 1) DO
    aPointTable[diIdx].xForce := TRUE;
END_FOR
