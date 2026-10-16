coUnit.TEST('ClockValidityRange');

AssertTrue(Condition := F_IiotClockValid(uliTs_ms := 1577836800000), Message := 'lower bound');
AssertFalse(Condition := F_IiotClockValid(uliTs_ms := 1577836799999), Message := 'before 2020');
AssertTrue(Condition := F_IiotClockValid(uliTs_ms := 4102444800000), Message := 'upper bound');
AssertFalse(Condition := F_IiotClockValid(uliTs_ms := 4102444800001), Message := 'after 2100');
AssertFalse(Condition := F_IiotClockValid(uliTs_ms := 0), Message := 'clock not set');

coUnit.TEST_FINISHED();
