coUnit.TEST('OverflowIsReportedNotTruncatedSilently');

fbJson.Begin();
FOR iField := 1 TO 40 DO
    fbJson.AddString(sKey := 'key_with_some_length', sValue := 'value with some length to fill the buffer');
END_FOR
AssertFalse(Condition := fbJson.Finish(), Message := 'Finish must fail after overflow');
AssertTrue(Condition := fbJson.xOverflow, Message := 'overflow flag must be set');
AssertEquals_UINT(Expected := GVL_Const.MQTT_PAYLOAD_LEN, Actual := fbJson.uiLen,
                  Message := 'buffer is filled up to its size and not beyond');

coUnit.TEST_FINISHED();
