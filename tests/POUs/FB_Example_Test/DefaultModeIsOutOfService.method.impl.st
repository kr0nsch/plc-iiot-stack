coUnit.TEST('DefaultModeIsOutOfService');

fbDut(rValue_pct := R_LOW_PCT, xValueValid := TRUE);
AssertFalse(Condition := fbDut.xOut,
            Message := 'Default mode must be OutOfService: output off');

coUnit.TEST_FINISHED();
