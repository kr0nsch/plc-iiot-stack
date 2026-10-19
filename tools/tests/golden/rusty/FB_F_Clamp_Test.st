(*
    Назначение: тесты CfUnit для F_Clamp — граничные условия и перепутанные границы
    Автор: kr0nsch
    Версия: 1.0.0
    Документ: docs/TEST_REPORT.md
*)
FUNCTION_BLOCK FB_F_Clamp_Test EXTENDS FB_TestSuite
VAR
END_VAR
METHOD PRIVATE SwappedLimits
VAR
    rResult : REAL;
END_VAR
TEST('SwappedLimits');
rResult := F_Clamp(rValue := 5.0, rMin := 10.0, rMax := 0.0);
AssertEquals_REAL(Expected := 10.0, Actual := rResult, Delta := 0.001, Message := 'swapped limits give min');
TEST_FINISHED();
END_METHOD
METHOD PRIVATE ValueBelowMin
VAR
    rResult : REAL;
END_VAR
TEST('ValueBelowMin');
rResult := F_Clamp(rValue := -5.0, rMin := 0.0, rMax := 10.0);
AssertEquals_REAL(Expected := 0.0, Actual := rResult, Delta := 0.001, Message := 'below min gives min');
TEST_FINISHED();
END_METHOD
METHOD PRIVATE ValueInsideRange
VAR
    rResult : REAL;
END_VAR
TEST('ValueInsideRange');
rResult := F_Clamp(rValue := 5.0, rMin := 0.0, rMax := 10.0);
AssertEquals_REAL(Expected := 5.0, Actual := rResult, Delta := 0.001, Message := 'value inside range');
TEST_FINISHED();
END_METHOD
ValueInsideRange();
ValueBelowMin();
SwappedLimits();
END_FUNCTION_BLOCK
