coUnit.TEST('RejectsTrailingCharacters');

sJsonIn := '{"a":1} x';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'trailing characters');
AssertTrue(Condition := fbParser.eError = E_JsonError.Trailing, Message := 'trailing -> Trailing');
AssertEquals_UINT(Expected := 8, Actual := fbParser.uiErrorPos, Message := 'error position');

coUnit.TEST_FINISHED();
