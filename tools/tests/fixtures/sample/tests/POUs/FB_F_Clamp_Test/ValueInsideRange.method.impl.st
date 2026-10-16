TEST('ValueInsideRange');
rResult := F_Clamp(rValue := 5.0, rMin := 0.0, rMax := 10.0);
AssertEquals_REAL(Expected := 5.0, Actual := rResult, Delta := 0.001, Message := 'value inside range');
TEST_FINISHED();
