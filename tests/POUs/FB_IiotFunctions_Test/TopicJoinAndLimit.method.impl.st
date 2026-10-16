coUnit.TEST('TopicJoinAndLimit');

AssertEquals_STRING(Expected := 'vodokanal/kns1/station/LT101/level',
                    Actual := F_IiotTopic(sPrefix := 'vodokanal/kns1/station', sPath := 'LT101/level'),
                        Message := 'join');
AssertEquals_STRING(Expected := 'x/y', Actual := F_IiotTopic(sPrefix := '', sPath := 'x/y'), Message := 'no prefix');
AssertEquals_INT(Expected := 127,
    Actual := LEN(F_IiotTopic(sPrefix := '123456789012345678901234567890123456789012345678901234567890123',
                              sPath := '123456789012345678901234567890123456789012345678901234567890123')),
    Message := '63 + 1 + 63 = 127 characters fit');
AssertEquals_STRING(Expected := '',
    Actual := F_IiotTopic(sPrefix := '123456789012345678901234567890123456789012345678901234567890123',
                          sPath := '1234567890123456789012345678901234567890123456789012345678901234'),
    Message := '63 + 1 + 64 = 128 characters do not fit');

coUnit.TEST_FINISHED();
