coUnit.TEST('AboveHighReturnsHigh');

rResult := F_Clamp(rValue := R_ABOVE, rLow := R_LOW, rHigh := R_HIGH);
AssertEquals_REAL(Expected := R_HIGH,
                  Actual := rResult,
                  Delta := R_DELTA,
                  Message := 'Value above range must be clamped to rHigh');

coUnit.TEST_FINISHED();
