coUnit.TEST('RejectsNestedObjectsAndArrays');

sJsonIn := '{"a":{"b":1}}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'nested object');
AssertTrue(Condition := fbParser.eError = E_JsonError.Nested, Message := 'nested object -> Nested');
sJsonIn := '{"a":[1,2]}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := 'array');
AssertTrue(Condition := fbParser.eError = E_JsonError.Nested, Message := 'array -> Nested');

coUnit.TEST_FINISHED();
