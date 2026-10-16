coUnit.TEST('NonFiniteTransitionsAreChanges');

pBits := ADR(lwNan);
lrNan := pBits^;
pBits := ADR(lwInf);
lrInf := pBits^;
AssertTrue(Condition := F_IiotDeadbandExceeded(lrNew := lrNan, lrLast := 1.0, rDeadband := 0.5), Message := 'to NaN');
AssertTrue(Condition := F_IiotDeadbandExceeded(lrNew := 1.0, lrLast := lrNan, rDeadband := 0.5), Message := 'from NaN');
AssertFalse(Condition := F_IiotDeadbandExceeded(lrNew := lrNan, lrLast := lrNan, rDeadband := 0.5),
            Message := 'NaN to NaN');
AssertFalse(Condition := F_IiotDeadbandExceeded(lrNew := lrInf, lrLast := lrNan, rDeadband := 0.5),
            Message := 'NaN to Inf');
AssertFalse(Condition := F_IsFiniteLreal(lrValue := lrInf), Message := 'Inf is not finite');
AssertTrue(Condition := F_IsFiniteLreal(lrValue := -1.0E300), Message := 'large negative is finite');

coUnit.TEST_FINISHED();
