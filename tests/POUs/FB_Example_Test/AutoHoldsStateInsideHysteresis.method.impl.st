coUnit.TEST('AutoHoldsStateInsideHysteresis');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_BAND_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
AssertTrue(Condition := fbDut.xOut,
           Message := 'Auto: output must stay on inside the hysteresis band');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_HIGH_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
AssertFalse(Condition := fbDut.xOut,
            Message := 'Auto: value above setpoint must switch the output off');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_BAND_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
AssertFalse(Condition := fbDut.xOut,
            Message := 'Auto: output must stay off inside the hysteresis band');

coUnit.TEST_FINISHED();
