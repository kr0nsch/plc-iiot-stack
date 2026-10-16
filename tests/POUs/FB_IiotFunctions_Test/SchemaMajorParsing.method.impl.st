coUnit.TEST('SchemaMajorParsing');

AssertEquals_INT(Expected := 1, Actual := F_IiotSchemaMajor(sVersion := '1.0'), Message := '1.0');
AssertEquals_INT(Expected := 1, Actual := F_IiotSchemaMajor(sVersion := '1.12'), Message := '1.12');
AssertEquals_INT(Expected := 2, Actual := F_IiotSchemaMajor(sVersion := '2.0'), Message := '2.0');
AssertEquals_INT(Expected := 10, Actual := F_IiotSchemaMajor(sVersion := '10.3'), Message := '10.3');
AssertEquals_INT(Expected := 0, Actual := F_IiotSchemaMajor(sVersion := '0.9'), Message := '0.9');
AssertEquals_INT(Expected := -1, Actual := F_IiotSchemaMajor(sVersion := '1'), Message := 'no minor');
AssertEquals_INT(Expected := -1, Actual := F_IiotSchemaMajor(sVersion := '1.'), Message := 'empty minor');
AssertEquals_INT(Expected := -1, Actual := F_IiotSchemaMajor(sVersion := '01.0'), Message := 'leading zero major');
AssertEquals_INT(Expected := -1, Actual := F_IiotSchemaMajor(sVersion := '1.01'), Message := 'leading zero minor');
AssertEquals_INT(Expected := -1, Actual := F_IiotSchemaMajor(sVersion := '1.0.0'), Message := 'three parts');
AssertEquals_INT(Expected := -1, Actual := F_IiotSchemaMajor(sVersion := 'v1.0'), Message := 'letter');
AssertEquals_INT(Expected := -1, Actual := F_IiotSchemaMajor(sVersion := ''), Message := 'empty');

coUnit.TEST_FINISHED();
