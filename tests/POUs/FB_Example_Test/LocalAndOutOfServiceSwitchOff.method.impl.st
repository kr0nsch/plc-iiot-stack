coUnit.TEST('LocalAndOutOfServiceSwitchOff');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
fbDut(eMode := E_DeviceMode.Local);
AssertFalse(Condition := fbDut.xOut,
            Message := 'Local: PLC command must be removed');

fbDut(eMode := E_DeviceMode.OutOfService, xManualOn := TRUE);
AssertFalse(Condition := fbDut.xOut,
            Message := 'OutOfService: output must stay off');

coUnit.TEST_FINISHED();
