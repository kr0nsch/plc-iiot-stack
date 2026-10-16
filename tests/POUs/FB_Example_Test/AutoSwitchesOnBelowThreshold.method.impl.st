coUnit.TEST('AutoSwitchesOnBelowThreshold');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
AssertTrue(Condition := fbDut.xOut,
           Message := 'Auto: value below on-threshold must switch the output on');
AssertFalse(Condition := fbDut.xFault,
            Message := 'Auto: valid measurement must not latch a fault');

coUnit.TEST_FINISHED();
