coUnit.TEST('AcceptsWhitespaceAndEmptyObject');

sJsonIn := ' { } ';
AssertTrue(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'empty object with spaces');
AssertEquals_UINT(Expected := 0, Actual := fbParser.uiCount, Message := 'no fields');
sJsonIn := '$T{ "a" :$N1 ,$R$N"b":"x" }$N';
AssertTrue(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'whitespace between tokens');
AssertEquals_UINT(Expected := 2, Actual := fbParser.uiCount, Message := 'two fields');

coUnit.TEST_FINISHED();
