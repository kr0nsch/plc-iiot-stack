coUnit.TEST('CountsSwitchOnsAndResetClears');

fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_HIGH_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
fbDut(eMode := E_DeviceMode.Auto, rValue_pct := R_LOW_PCT, xValueValid := TRUE,
      rSetpoint_pct := R_SP_PCT, rHysteresis_pct := R_HYST_PCT);
AssertEquals_UDINT(Expected := UDI_TWO_SWITCH_ONS,
                   Actual := fbDut.Count,
                   Message := 'Count must increase on rising edges of the output only');
AssertTrue(Condition := fbDut.xOut,
           Message := 'Output must be on before Reset');

itfDut := fbDut;
xResetResult := itfDut.Reset();
AssertTrue(Condition := xResetResult,
           Message := 'Reset via I_Resettable must return TRUE');
AssertFalse(Condition := fbDut.xOut,
            Message := 'Reset must switch the output off');
AssertEquals_UDINT(Expected := 0,
                   Actual := fbDut.Count,
                   Message := 'Reset must clear the switch-on counter');

coUnit.TEST_FINISHED();
