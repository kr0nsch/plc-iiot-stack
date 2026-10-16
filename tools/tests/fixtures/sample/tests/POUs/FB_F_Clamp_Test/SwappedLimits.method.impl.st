TEST('SwappedLimits');
rResult := F_Clamp(rValue := 5.0, rMin := 10.0, rMax := 0.0);
AssertEquals_REAL(Expected := 10.0, Actual := rResult, Delta := 0.001, Message := 'swapped limits give min');
TEST_FINISHED();
