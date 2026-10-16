coUnit.TEST('LimitsKeyAndValueLength');

sJsonIn := '{"1234567890123456789012345678901":1}';
AssertTrue(Condition := fbParser.Parse(sJson := sJsonIn), Message := '31-char key fits');
sJsonIn := '{"12345678901234567890123456789012":1}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := '32-char key');
AssertTrue(Condition := fbParser.eError = E_JsonError.KeyTooLong, Message := 'key too long');
sJsonIn := '{"v":"1234567890123456789012345678901234567890123456789012345678901234"}';
AssertTrue(Condition := fbParser.Parse(sJson := sJsonIn), Message := '64-char value fits');
sJsonIn := '{"v":"12345678901234567890123456789012345678901234567890123456789012345"}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := '65-char value');
AssertTrue(Condition := fbParser.eError = E_JsonError.ValueTooLong, Message := 'value too long');

coUnit.TEST_FINISHED();
