coUnit.TEST('AtHighBoundaryReturnsHigh');

rResult := F_Clamp(rValue := R_HIGH, rLow := R_LOW, rHigh := R_HIGH);
AssertEquals_REAL(Expected := R_HIGH,
                  Actual := rResult,
                  Delta := R_DELTA,
                  Message := 'Value equal to rHigh must be returned as is');

coUnit.TEST_FINISHED();
