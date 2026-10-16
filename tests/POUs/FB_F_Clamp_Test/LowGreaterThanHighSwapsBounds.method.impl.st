coUnit.TEST('LowGreaterThanHighSwapsBounds');

rResult := F_Clamp(rValue := R_INSIDE, rLow := R_HIGH, rHigh := R_LOW);
AssertEquals_REAL(Expected := R_INSIDE,
                  Actual := rResult,
                  Delta := R_DELTA,
                  Message := 'Swapped bounds: value inside must be returned unchanged');

rResult := F_Clamp(rValue := R_BELOW, rLow := R_HIGH, rHigh := R_LOW);
AssertEquals_REAL(Expected := R_LOW,
                  Actual := rResult,
                  Delta := R_DELTA,
                  Message := 'Swapped bounds: value below must be clamped to the smaller bound');

rResult := F_Clamp(rValue := R_ABOVE, rLow := R_HIGH, rHigh := R_LOW);
AssertEquals_REAL(Expected := R_HIGH,
                  Actual := rResult,
                  Delta := R_DELTA,
                  Message := 'Swapped bounds: value above must be clamped to the larger bound');

coUnit.TEST_FINISHED();
