coUnit.TEST('IntExtremes');

fbJson.Begin();
fbJson.AddInt(sKey := 'z', liValue := 0);
fbJson.AddInt(sKey := 'max', liValue := LINT#9223372036854775807);
fbJson.AddInt(sKey := 'min', liValue := LINT#-9223372036854775807 - 1);
fbJson.AddInt(sKey := 'ts', liValue := LINT#1792137600250);
fbJson.Finish();
AssertEquals_STRING(Expected := '{"z":0,"max":9223372036854775807,"min":-9223372036854775808,"ts":1792137600250}',
                    Actual := fbJson.sJson, Message := 'LINT extremes');

coUnit.TEST_FINISHED();
