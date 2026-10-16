coUnit.TEST('RealFromRealIsRoundedLikeTheValueShown');

fbJson.Begin();
fbJson.AddReal(sKey := 'v', lrValue := rValue, uiDecimals := 3);
fbJson.Finish();
AssertEquals_STRING(Expected := '{"v":2.35}', Actual := fbJson.sJson, Message := 'REAL widened to LREAL and rounded');

coUnit.TEST_FINISHED();
