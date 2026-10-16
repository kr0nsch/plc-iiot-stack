coUnit.TEST('AcknowledgeClearsFaultWhenValid');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := FALSE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
xAckResult := fbDut.Acknowledge();
AssertTrue(Condition := xAckResult,
           Message := 'Acknowledge must return TRUE when the measurement is valid');
AssertFalse(Condition := fbDut.xFault,
            Message := 'Acknowledge must clear the fault when the measurement is valid');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
AssertTrue(Condition := fbDut.xOut,
           Message := 'After acknowledge the output must follow the measurement again');

coUnit.TEST_FINISHED();
