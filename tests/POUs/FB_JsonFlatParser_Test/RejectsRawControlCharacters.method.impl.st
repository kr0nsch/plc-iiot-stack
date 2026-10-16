coUnit.TEST('RejectsRawControlCharacters');

sJsonIn := '{"s":"a$Tb"}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'raw tab inside string');
AssertTrue(Condition := fbParser.eError = E_JsonError.Syntax, Message := 'raw control -> Syntax');

coUnit.TEST_FINISHED();
