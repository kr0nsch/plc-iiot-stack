coUnit.TEST('NowIsMonotonic');

ltFirst := F_IiotNow();
ltSecond := F_IiotNow();
AssertTrue(Condition := ltFirst > LTIME#0S, Message := 'time since start is positive');
AssertTrue(Condition := ltSecond >= ltFirst, Message := 'second call is not earlier');

coUnit.TEST_FINISHED();
