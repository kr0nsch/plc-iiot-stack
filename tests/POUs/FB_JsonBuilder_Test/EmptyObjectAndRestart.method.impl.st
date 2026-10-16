coUnit.TEST('EmptyObjectAndRestart');

fbJson.Begin();
fbJson.AddInt(sKey := 'old', liValue := 1);
fbJson.Finish();
fbJson.Begin();
AssertTrue(Condition := fbJson.Finish(), Message := 'empty object is complete');
AssertEquals_STRING(Expected := '{}', Actual := fbJson.sJson, Message := 'Begin must clear the previous text');

coUnit.TEST_FINISHED();
