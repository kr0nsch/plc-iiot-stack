coUnit.TEST('PeriodRepublishesAll');

Setup(fbClient := fbFake, aPointTable := aPts);
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H, xReadyIn := TRUE);
fbFake.ClearPublished();
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#9S999MS, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 0, Actual := fbFake.uiPubCount, Message := 'before the period');
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#10S, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 4, Actual := fbFake.uiPubCount, Message := 'all metrics at the period');
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#15S, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 4, Actual := fbFake.uiPubCount, Message := 'period restarts');

coUnit.TEST_FINISHED();
