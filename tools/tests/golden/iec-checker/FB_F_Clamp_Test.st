(*
    Назначение: тесты CfUnit для F_Clamp — граничные условия и перепутанные границы
    Автор: <ИМЯ ФАМИЛИЯ>
    Версия: 1.0.0
    Документ: docs/TEST_REPORT.md
*)
FUNCTION_BLOCK FB_F_Clamp_Test
VAR
END_VAR
ValueInsideRange();
ValueBelowMin();
SwappedLimits();
END_FUNCTION_BLOCK

FUNCTION FB_F_Clamp_Test__SwappedLimits : BOOL
VAR
    rResult : REAL;
END_VAR
TEST('SwappedLimits');
rResult := F_Clamp(rValue := 5.0, rMin := 10.0, rMax := 0.0);
AssertEquals_REAL(Expected := 10.0, Actual := rResult, Delta := 0.001, Message := 'swapped$20limits$20give$20min');
TEST_FINISHED();
FB_F_Clamp_Test__SwappedLimits := TRUE;
END_FUNCTION

FUNCTION FB_F_Clamp_Test__ValueBelowMin : BOOL
VAR
    rResult : REAL;
END_VAR
TEST('ValueBelowMin');
rResult := F_Clamp(rValue := -5.0, rMin := 0.0, rMax := 10.0);
AssertEquals_REAL(Expected := 0.0, Actual := rResult, Delta := 0.001, Message := 'below$20min$20gives$20min');
TEST_FINISHED();
FB_F_Clamp_Test__ValueBelowMin := TRUE;
END_FUNCTION

FUNCTION FB_F_Clamp_Test__ValueInsideRange : BOOL
VAR
    rResult : REAL;
END_VAR
TEST('ValueInsideRange');
rResult := F_Clamp(rValue := 5.0, rMin := 0.0, rMax := 10.0);
AssertEquals_REAL(Expected := 5.0, Actual := rResult, Delta := 0.001, Message := 'value$20inside$20range');
TEST_FINISHED();
FB_F_Clamp_Test__ValueInsideRange := TRUE;
END_FUNCTION
