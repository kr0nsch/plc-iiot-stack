coUnit.TEST('EqualBoundsReturnsBound');

rResult := F_Clamp(rValue := R_INSIDE, rLow := R_HIGH, rHigh := R_HIGH);
AssertEquals_REAL(Expected := R_HIGH,
                  Actual := rResult,
                  Delta := R_DELTA,
                  Message := 'Value below degenerate range must give the bound');

rResult := F_Clamp(rValue := R_ABOVE, rLow := R_HIGH, rHigh := R_HIGH);
AssertEquals_REAL(Expected := R_HIGH,
                  Actual := rResult,
                  Delta := R_DELTA,
                  Message := 'Value above degenerate range must give the bound');

coUnit.TEST_FINISHED();
