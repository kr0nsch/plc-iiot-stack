coUnit.TEST('CmdIdNameAndOriginPatterns');

AssertTrue(Condition := F_IiotIsCmdId(sText := 'b0e7c3d1-5a2f-4e8b-8c61-9d4a7f2e1b33'), Message := 'UUID, 36 chars');
AssertTrue(Condition := F_IiotIsCmdId(sText := 'abc_1234'), Message := '8 chars');
AssertFalse(Condition := F_IiotIsCmdId(sText := 'abc1234'), Message := '7 chars');
AssertFalse(Condition := F_IiotIsCmdId(sText := '1234567890123456789012345678901234567'), Message := '37 chars');
AssertFalse(Condition := F_IiotIsCmdId(sText := 'abc 1234'), Message := 'space');
AssertTrue(Condition := F_IiotIsName(sText := 'P101', iMaxLen := 16, xUpperOnly := TRUE), Message := 'device P101');
AssertTrue(Condition := F_IiotIsName(sText := 'P_1', iMaxLen := 16, xUpperOnly := TRUE), Message := 'device P_1');
AssertFalse(Condition := F_IiotIsName(sText := 'p101', iMaxLen := 16, xUpperOnly := TRUE), Message := 'lower device');
AssertFalse(Condition := F_IiotIsName(sText := '1P', iMaxLen := 16, xUpperOnly := TRUE), Message := 'digit first');
AssertFalse(Condition := F_IiotIsName(sText := 'ABCDEFGHIJKLMNOPQ', iMaxLen := 16, xUpperOnly := TRUE),
            Message := '17 chars');
AssertTrue(Condition := F_IiotIsName(sText := 'SpeedSp', iMaxLen := 31, xUpperOnly := FALSE), Message := 'command');
AssertFalse(Condition := F_IiotIsName(sText := 'Speed-Sp', iMaxLen := 31, xUpperOnly := FALSE), Message := 'dash');
AssertFalse(Condition := F_IiotIsName(sText := '', iMaxLen := 31, xUpperOnly := FALSE), Message := 'empty');
AssertTrue(Condition := F_IiotIsPrintable(sText := 'operator1@grafana', iMaxLen := 64), Message := 'origin');
AssertFalse(Condition := F_IiotIsPrintable(sText := '', iMaxLen := 64), Message := 'empty origin');
AssertFalse(Condition := F_IiotIsPrintable(sText := 'a$Nb', iMaxLen := 64), Message := 'control char');
AssertTrue(Condition := F_IiotIsPrintable(sText := '1234567890123456789012345678901234567890123456789012345678901234',
                                          iMaxLen := 64), Message := '64 chars');

coUnit.TEST_FINISHED();
