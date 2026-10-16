coUnit.TEST('EscapesSpecialCharacters');

fbJson.Begin();
fbJson.AddString(sKey := 'k"', sValue := 'a"b\c$Nd$Te$Rf$01');
fbJson.Finish();
AssertEquals_STRING(Expected := '{"k\"":"a\"b\\c\nd\te\rf\u0001"}', Actual := fbJson.sJson,
                    Message := 'quote, backslash and control characters must be escaped');

coUnit.TEST_FINISHED();
