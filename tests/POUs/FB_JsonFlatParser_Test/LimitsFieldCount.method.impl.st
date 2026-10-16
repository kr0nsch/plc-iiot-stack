coUnit.TEST('LimitsFieldCount');

sJsonIn := '{"a":1,"b":2,"c":3,"d":4,"e":5,"f":6,"g":7,"h":8,"i":9,"j":10,"k":11,"l":12}';
AssertTrue(Condition := fbParser.Parse(sJson := sJsonIn), Message := '12 fields fit');
sJsonIn := '{"a":1,"b":2,"c":3,"d":4,"e":5,"f":6,"g":7,"h":8,"i":9,"j":10,"k":11,"l":12,"m":13}';
AssertFalse(Condition := fbParser.Parse(sJson := sJsonIn), Message := '13 fields');
AssertTrue(Condition := fbParser.eError = E_JsonError.TooManyFields, Message := 'too many fields');

coUnit.TEST_FINISHED();
