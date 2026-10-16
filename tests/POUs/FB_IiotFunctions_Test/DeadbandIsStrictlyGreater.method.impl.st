coUnit.TEST('DeadbandIsStrictlyGreater');

AssertFalse(Condition := F_IiotDeadbandExceeded(lrNew := 10.5, lrLast := 10.0, rDeadband := 0.5),
            Message := 'change equal to deadband must not trigger');
AssertTrue(Condition := F_IiotDeadbandExceeded(lrNew := 10.51, lrLast := 10.0, rDeadband := 0.5),
           Message := 'change above deadband must trigger');
AssertFalse(Condition := F_IiotDeadbandExceeded(lrNew := 9.5, lrLast := 10.0, rDeadband := 0.5),
            Message := 'negative change equal to deadband must not trigger');
AssertTrue(Condition := F_IiotDeadbandExceeded(lrNew := 9.49, lrLast := 10.0, rDeadband := 0.5),
           Message := 'negative change above deadband must trigger');
AssertTrue(Condition := F_IiotDeadbandExceeded(lrNew := 1.0E300, lrLast := -1.0E300, rDeadband := 1.0),
           Message := 'large difference must not overflow');

coUnit.TEST_FINISHED();
