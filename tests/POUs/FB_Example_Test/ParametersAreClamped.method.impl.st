coUnit.TEST('ParametersAreClamped');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_TOO_HIGH_PCT, rHysteresis_pct := R_HYST_TOO_LOW_PCT);
AssertEquals_REAL(Expected := GVL_Const.EXAMPLE_SP_MAX_PCT,
                  Actual := fbDut.rSetpointUsed_pct,
                  Delta := R_DELTA,
                  Message := 'Setpoint above range must be clamped to EXAMPLE_SP_MAX_PCT');
AssertEquals_REAL(Expected := GVL_Const.EXAMPLE_HYST_MIN_PCT,
                  Actual := fbDut.rHysteresisUsed_pct,
                  Delta := R_DELTA,
                  Message := 'Hysteresis below range must be clamped to EXAMPLE_HYST_MIN_PCT');

coUnit.TEST_FINISHED();
