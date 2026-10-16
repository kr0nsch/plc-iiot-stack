coUnit.TEST('AlarmStateFromWords');

stWords.wActive := 16#0008;      // слот 3
stWords.wUnack := 16#0008;
AssertTrue(Condition := F_IiotAlarmStateOf(stWords := stWords, uiSlot := 3) = E_IiotAlarmState.ActiveUnack,
           Message := 'active and unacked');
AssertTrue(Condition := F_IiotAlarmStateOf(stWords := stWords, uiSlot := 2) = E_IiotAlarmState.Normal,
           Message := 'other slot is normal');
stWords.wUnack := 0;
AssertTrue(Condition := F_IiotAlarmStateOf(stWords := stWords, uiSlot := 3) = E_IiotAlarmState.ActiveAck,
           Message := 'active and acked');
stWords.wActive := 0;
stWords.wUnack := 16#0008;
AssertTrue(Condition := F_IiotAlarmStateOf(stWords := stWords, uiSlot := 3) = E_IiotAlarmState.RtnUnack,
           Message := 'returned unacked');
stWords.wShelved := 16#0008;
AssertTrue(Condition := F_IiotAlarmStateOf(stWords := stWords, uiSlot := 3) = E_IiotAlarmState.Shelved,
           Message := 'shelved');
stWords.xOutOfService := TRUE;
AssertTrue(Condition := F_IiotAlarmStateOf(stWords := stWords, uiSlot := 3) = E_IiotAlarmState.OutOfService,
           Message := 'out of service');

coUnit.TEST_FINISHED();
