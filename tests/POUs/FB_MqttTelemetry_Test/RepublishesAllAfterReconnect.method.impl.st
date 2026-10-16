coUnit.TEST('RepublishesAllAfterReconnect');

Setup(fbClient := fbFake, aPointTable := aPts);
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H, xReadyIn := TRUE);
fbFake.ClearPublished();
fbFake.xLinkUp := FALSE;
aPts[1].lrValue := 3.0;
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#2S, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 0, Actual := fbFake.uiPubCount + fbFake.uiPubRejected,
    Message := 'no attempts without link');
fbFake.xLinkUp := TRUE;
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#3S, xReadyIn := FALSE);
AssertEquals_UINT(Expected := 0, Actual := fbFake.uiPubCount, Message := 'waits for the new birth');
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#3S, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 4, Actual := fbFake.uiPubCount, Message := 'all metrics after reconnect');

coUnit.TEST_FINISHED();
