coUnit.TEST('ParsesFlatObjectWithAllTypes');

sJsonIn := '{"s":"abc","n":-12.5e1,"t":true,"f":false,"z":null}';
AssertTrue(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'valid object must parse');
AssertEquals_UINT(Expected := 5, Actual := fbParser.uiCount, Message := 'field count');
AssertTrue(Condition := fbParser.GetString(sKey := 's', sValue := sText), Message := 'string field');
AssertEquals_STRING(Expected := 'abc', Actual := sText, Message := 'string value');
AssertTrue(Condition := fbParser.GetNumber(sKey := 'n', lrValue := lrNum), Message := 'number field');
AssertEquals_LREAL(Expected := -125.0, Actual := lrNum, Delta := 1.0E-9, Message := 'number value with exponent');
AssertTrue(Condition := fbParser.GetBool(sKey := 't', xValue := xFlag) AND xFlag, Message := 'true');
AssertTrue(Condition := fbParser.GetBool(sKey := 'f', xValue := xFlag) AND NOT xFlag, Message := 'false');
AssertTrue(Condition := fbParser.FieldType(sKey := 'z') = E_JsonType.NullValue, Message := 'null');
AssertTrue(Condition := fbParser.FieldType(sKey := 'nope') = E_JsonType.Missing, Message := 'missing key');
AssertFalse(Condition := fbParser.GetString(sKey := 'n', sValue := sText), Message := 'number is not a string');
AssertFalse(Condition := fbParser.GetNumber(sKey := 's', lrValue := lrNum), Message := 'string is not a number');
AssertEquals_STRING(Expected := 'n', Actual := fbParser.KeyAt(uiIdx := 2), Message := 'key by index');
AssertEquals_STRING(Expected := '', Actual := fbParser.KeyAt(uiIdx := 6), Message := 'key index out of range');

coUnit.TEST_FINISHED();
