coUnit.TEST('ZeroNegativeOrNanDeadbandMeansAnyChange');

pBitsR := ADR(dwNan);
rNan := pBitsR^;
AssertFalse(Condition := F_IiotDeadbandExceeded(lrNew := 1.0, lrLast := 1.0, rDeadband := 0.0), Message := 'no change');
AssertTrue(Condition := F_IiotDeadbandExceeded(lrNew := 1.0001, lrLast := 1.0, rDeadband := 0.0),
           Message := 'zero deadband: any change');
AssertTrue(Condition := F_IiotDeadbandExceeded(lrNew := 2.0, lrLast := 1.0, rDeadband := -1.0),
           Message := 'negative deadband: any change');
AssertTrue(Condition := F_IiotDeadbandExceeded(lrNew := 1.5, lrLast := 1.0, rDeadband := rNan),
           Message := 'NaN deadband: any change');
AssertFalse(Condition := F_IiotDeadbandExceeded(lrNew := 1.0, lrLast := 1.0, rDeadband := rNan),
            Message := 'NaN deadband: no change');

coUnit.TEST_FINISHED();
