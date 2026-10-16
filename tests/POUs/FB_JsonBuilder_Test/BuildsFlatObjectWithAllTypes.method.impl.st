coUnit.TEST('BuildsFlatObjectWithAllTypes');

fbJson.Begin();
fbJson.AddString(sKey := 'a', sValue := 'x');
fbJson.AddInt(sKey := 'n', liValue := -42);
fbJson.AddBool(sKey := 'b', xValue := TRUE);
fbJson.AddBool(sKey := 'c', xValue := FALSE);
fbJson.AddNull(sKey := 'z');
fbJson.AddReal(sKey := 'r', lrValue := 2.35, uiDecimals := 3);
AssertTrue(Condition := fbJson.Finish(), Message := 'Finish must report a complete object');
AssertEquals_STRING(Expected := '{"a":"x","n":-42,"b":true,"c":false,"z":null,"r":2.35}',
                    Actual := fbJson.sJson, Message := 'flat object text');
AssertEquals_UINT(Expected := 54, Actual := fbJson.uiLen, Message := 'length must match the text');

coUnit.TEST_FINISHED();
