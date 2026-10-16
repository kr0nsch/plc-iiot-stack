coUnit.TEST('InvalidValueLatchesFault');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := FALSE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
AssertTrue(Condition := fbDut.xFault,
           Message := 'Auto: invalid measurement must latch a fault');
AssertFalse(Condition := fbDut.xOut,
            Message := 'Auto: fault must switch the output off (safe state)');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
AssertTrue(Condition := fbDut.xFault,
           Message := 'Fault must stay latched after the measurement recovers');
AssertFalse(Condition := fbDut.xOut,
            Message := 'Output must stay off until the fault is acknowledged');

coUnit.TEST_FINISHED();
