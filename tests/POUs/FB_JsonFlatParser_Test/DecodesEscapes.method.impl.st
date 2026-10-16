coUnit.TEST('DecodesEscapes');

sJsonIn := '{"s":"a\"b\\c\/d\n\u0041\t"}';
AssertTrue(Condition := fbParser.Parse(sJson := sJsonIn) AND fbParser.GetString(sKey := 's', sValue := sText),
           Message := 'escapes must parse');
AssertEquals_STRING(Expected := 'a"b\c/d$NA$T', Actual := sText, Message := 'decoded escapes');
sJsonIn := '{"s":"\u0410"}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'non-ASCII escape');
AssertTrue(Condition := fbParser.eError = E_JsonError.BadEscape, Message := 'non-ASCII -> BadEscape');
sJsonIn := '{"s":"\u0000"}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'NUL escape');
sJsonIn := '{"s":"\x"}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'unknown escape');
AssertTrue(Condition := fbParser.eError = E_JsonError.BadEscape, Message := 'unknown -> BadEscape');
sJsonIn := '{"s":"\u00"}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'short escape');

coUnit.TEST_FINISHED();
