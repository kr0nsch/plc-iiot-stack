coUnit.TEST('RejectsDuplicateKeys');

sJsonIn := '{"a":1,"a":2}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'duplicate key');
AssertTrue(Condition := fbParser.eError = E_JsonError.Duplicate, Message := 'duplicate -> Duplicate');
AssertEquals_UINT(Expected := 0, Actual := fbParser.uiCount, Message := 'no fields after failure');

coUnit.TEST_FINISHED();
