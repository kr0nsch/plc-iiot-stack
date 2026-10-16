coUnit.TEST('AcknowledgeKeepsFaultWhileInvalid');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := FALSE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
xAckResult := fbDut.Acknowledge();
AssertFalse(Condition := xAckResult,
            Message := 'Acknowledge must return FALSE while the measurement is invalid');
AssertTrue(Condition := fbDut.xFault,
           Message := 'Acknowledge must keep the fault while the measurement is invalid');

coUnit.TEST_FINISHED();
