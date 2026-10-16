coUnit.TEST('BufferHoldsExactlyItsSize');

// поле "kkk":"<63 символа>" — 71 байт; «{» и 14 полей с запятыми — 1 + 14 * 71 + 13 = 1008 байт
fbJson.Begin();
FOR iField := 1 TO 14 DO
    fbJson.AddString(sKey := 'kkk', sValue := '123456789012345678901234567890123456789012345678901234567890123');
END_FOR
fbJson.AddString(sKey := 'q', sValue := '1234567');   // ,"q":"1234567" — 14 байт: 1022, «}» — 1023
AssertTrue(Condition := fbJson.Finish(), Message := 'object of exactly the buffer size must fit');
AssertEquals_UINT(Expected := 1023, Actual := fbJson.uiLen, Message := 'length equals buffer size');
fbJson.Begin();
FOR iField := 1 TO 14 DO
    fbJson.AddString(sKey := 'kkk', sValue := '123456789012345678901234567890123456789012345678901234567890123');
END_FOR
fbJson.AddString(sKey := 'q', sValue := '12345678');
AssertFalse(Condition := fbJson.Finish(), Message := 'one byte more must overflow');

coUnit.TEST_FINISHED();
