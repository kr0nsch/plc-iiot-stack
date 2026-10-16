coUnit.TEST('ManualFollowsCommand');

fbDut(eMode := E_DeviceMode.Manual, rValue_pct := R_HIGH_PCT, xValueValid := FALSE,
      xManualOn := TRUE);
AssertTrue(Condition := fbDut.xOut,
           Message := 'Manual: output must follow xManualOn = TRUE');
AssertFalse(Condition := fbDut.xFault,
            Message := 'Manual: invalid measurement must not latch a fault');

fbDut(eMode := E_DeviceMode.Manual, xManualOn := FALSE);
AssertFalse(Condition := fbDut.xOut,
            Message := 'Manual: output must follow xManualOn = FALSE');

coUnit.TEST_FINISHED();
