coUnit.TEST('TracksIntegerLiterals');

sJsonIn := '{"ts":1792137621000,"a":1.0,"b":1e3,"c":-7,"s":"9"}';
AssertTrue(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'object must parse');
AssertTrue(Condition := fbParser.FieldIsInteger(sKey := 'ts'), Message := '13-digit integer');
AssertTrue(Condition := fbParser.GetNumber(sKey := 'ts', lrValue := lrNum), Message := 'ts number');
AssertEquals_LREAL(Expected := 1792137621000.0, Actual := lrNum, Delta := 0.0, Message := 'ts exact in LREAL');
AssertFalse(Condition := fbParser.FieldIsInteger(sKey := 'a'), Message := '1.0 is not an integer literal');
AssertFalse(Condition := fbParser.FieldIsInteger(sKey := 'b'), Message := '1e3 is not an integer literal');
AssertTrue(Condition := fbParser.FieldIsInteger(sKey := 'c'), Message := 'negative integer');
AssertFalse(Condition := fbParser.FieldIsInteger(sKey := 's'), Message := 'string is not a number');

coUnit.TEST_FINISHED();
