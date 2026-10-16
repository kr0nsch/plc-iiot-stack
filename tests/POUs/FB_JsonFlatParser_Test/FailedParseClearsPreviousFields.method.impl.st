coUnit.TEST('FailedParseClearsPreviousFields');

sJsonIn := '{"a":1}';
fbParser.Parse(sJson := sJsonIn);
sJsonIn := '{"a":1,';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'second parse fails');
AssertEquals_UINT(Expected := 0, Actual := fbParser.FindField(sKey := 'a'), Message := 'old field must be gone');

coUnit.TEST_FINISHED();
