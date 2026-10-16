coUnit.TEST('DeadbandAndMinInterval');

Setup(fbClient := fbFake, aPointTable := aPts);
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H, xReadyIn := TRUE);
fbFake.ClearPublished();
aPts[1].lrValue := 2.355;
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#2S, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 0, Actual := fbFake.uiPubCount, Message := 'change 0.005 inside deadband 0.01');
aPts[1].lrValue := 2.37;
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#2S, xReadyIn := TRUE);
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/level', sPart := '"value":2.37,'),
           Message := 'change 0.02 beyond deadband');
aPts[1].lrValue := 2.5;
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#2S500MS, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 1, Actual := fbFake.uiPubCount, Message := 'no second message within a second');
AssertEquals_UINT(Expected := 0, Actual := fbTel.uiPending, Message := 'held by the interval, not queued');
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#3S, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 2, Actual := fbFake.uiPubCount, Message := 'published after the interval');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/level', sPart := '"value":2.5,'),
           Message := 'latest value');

coUnit.TEST_FINISHED();
