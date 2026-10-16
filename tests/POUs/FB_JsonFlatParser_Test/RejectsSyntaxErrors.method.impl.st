coUnit.TEST('RejectsSyntaxErrors');

sJsonIn := '';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'empty');
AssertTrue(Condition := fbParser.eError = E_JsonError.Empty, Message := 'empty -> Empty');
sJsonIn := '   ';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'only spaces');
AssertTrue(Condition := fbParser.eError = E_JsonError.Empty, Message := 'spaces -> Empty');
sJsonIn := '[1]';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'array at top');
AssertTrue(Condition := fbParser.eError = E_JsonError.Syntax, Message := 'array at top -> Syntax');
sJsonIn := '{"a":1';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'unterminated object');
sJsonIn := '{"a" 1}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'no colon');
sJsonIn := '{"a":1,}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'trailing comma');
sJsonIn := '{a:1}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'unquoted key');
sJsonIn := '{"a":tru}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'bad literal');
sJsonIn := '{"a":"x}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'unterminated string');
AssertTrue(Condition := fbParser.eError = E_JsonError.Syntax, Message := 'unterminated string -> Syntax');

coUnit.TEST_FINISHED();
