coUnit.TEST('AutoThresholdsAreInclusive');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_ON_THRESHOLD_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
AssertTrue(Condition := fbDut.xOut,
           Message := 'Auto: value equal to on-threshold must switch the output on');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_SP_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
AssertFalse(Condition := fbDut.xOut,
            Message := 'Auto: value equal to setpoint must switch the output off');

coUnit.TEST_FINISHED();
