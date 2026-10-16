coUnit.TEST('ValidatesNumberGrammarAndRange');

sJsonIn := '{"n":01}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'leading zero');
AssertTrue(Condition := fbParser.eError = E_JsonError.BadNumber, Message := 'leading zero -> BadNumber');
sJsonIn := '{"n":1.}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'dot without digits');
sJsonIn := '{"n":-}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'sign without digits');
sJsonIn := '{"n":1e}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'exponent without digits');
sJsonIn := '{"n":1e39}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'beyond REAL range');
AssertTrue(Condition := fbParser.eError = E_JsonError.BadNumber, Message := 'beyond REAL -> BadNumber');
sJsonIn := '{"n":1e1000}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'four exponent digits');
sJsonIn := '{"n":123456789012345678}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := '18 digits');
sJsonIn := '{"n":.5}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'no integer part');
sJsonIn := '{"n":0.5E-3}';
AssertTrue(Condition := fbParser.Parse(sJson := sJsonIn) AND fbParser.GetNumber(sKey := 'n', lrValue := lrNum),
           Message := 'fraction with negative exponent');
AssertEquals_LREAL(Expected := 0.0005, Actual := lrNum, Delta := 1.0E-12, Message := '0.5E-3');
sJsonIn := '{"n":-0.0}';
AssertTrue(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'negative zero');
sJsonIn := '{"n":1E+2}';
AssertTrue(Condition := fbParser.Parse(sJson := sJsonIn) AND fbParser.GetNumber(sKey := 'n', lrValue := lrNum),
           Message := 'exponent with plus');
AssertEquals_LREAL(Expected := 100.0, Actual := lrNum, Delta := 1.0E-9, Message := '1E+2');
sJsonIn := '{"n":12345678901234567}';
AssertTrue(Condition := fbParser.Parse(sJson := sJsonIn), Message := '17 digits are accepted');

coUnit.TEST_FINISHED();
