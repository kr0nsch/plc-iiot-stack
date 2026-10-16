coUnit.TEST('BelowLowReturnsLow');

rResult := F_Clamp(rValue := R_BELOW, rLow := R_LOW, rHigh := R_HIGH);
AssertEquals_REAL(Expected := R_LOW,
                  Actual := rResult,
                  Delta := R_DELTA,
                  Message := 'Value below range must be clamped to rLow');

coUnit.TEST_FINISHED();
