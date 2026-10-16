coUnit.TEST('IntExtremes');

// Границы LINT (2^63 - 1 и -2^63) записаны в шестнадцатеричном виде: десятичный литерал больше 2^62 - 1
// iec_checker 0.4 не читает (Failure int_of_string), и статанализ пропустил бы весь набор.
fbJson.Begin();
fbJson.AddInt(sKey := 'z', liValue := 0);
fbJson.AddInt(sKey := 'max', liValue := LINT#16#7FFFFFFFFFFFFFFF);
fbJson.AddInt(sKey := 'min', liValue := -LINT#16#7FFFFFFFFFFFFFFF - 1);
fbJson.AddInt(sKey := 'ts', liValue := LINT#1792137600250);
fbJson.Finish();
AssertEquals_STRING(Expected := '{"z":0,"max":9223372036854775807,"min":-9223372036854775808,"ts":1792137600250}',
                    Actual := fbJson.sJson, Message := 'LINT extremes');

coUnit.TEST_FINISHED();
