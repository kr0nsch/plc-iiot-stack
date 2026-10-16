coUnit.TEST('AtLowBoundaryReturnsLow');

rResult := F_Clamp(rValue := R_LOW, rLow := R_LOW, rHigh := R_HIGH);
AssertEquals_REAL(Expected := R_LOW,
                  Actual := rResult,
                  Delta := R_DELTA,
                  Message := 'Value equal to rLow must be returned as is');

coUnit.TEST_FINISHED();
