coUnit.TEST('InsideRangeReturnsValue');

rResult := F_Clamp(rValue := R_INSIDE, rLow := R_LOW, rHigh := R_HIGH);
AssertEquals_REAL(Expected := R_INSIDE,
                  Actual := rResult,
                  Delta := R_DELTA,
                  Message := 'Value inside range must be returned unchanged');

coUnit.TEST_FINISHED();
