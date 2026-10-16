coUnit.TEST('RealFormattingRoundsAndTrimsZeros');

fbJson.Begin();
fbJson.AddReal(sKey := 'a', lrValue := 1.0, uiDecimals := 3);
fbJson.AddReal(sKey := 'b', lrValue := 12345.678, uiDecimals := 1);
fbJson.AddReal(sKey := 'c', lrValue := 0.05, uiDecimals := 2);
fbJson.AddReal(sKey := 'd', lrValue := -3.5, uiDecimals := 1);
fbJson.AddReal(sKey := 'e', lrValue := -0.0001, uiDecimals := 3);
fbJson.AddReal(sKey := 'f', lrValue := 0.001, uiDecimals := 3);
fbJson.AddReal(sKey := 'g', lrValue := 7.4, uiDecimals := 0);
fbJson.AddReal(sKey := 'h', lrValue := 0.1234567, uiDecimals := 10);
fbJson.Finish();
AssertEquals_STRING(Expected := '{"a":1,"b":12345.7,"c":0.05,"d":-3.5,"e":0,"f":0.001,"g":7,"h":0.123457}',
                    Actual := fbJson.sJson, Message := 'number formatting');

coUnit.TEST_FINISHED();
