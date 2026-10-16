coUnit.TEST('WaitsForBirthAndClock');

Setup(fbClient := fbFake, aPointTable := aPts);
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H, xReadyIn := FALSE);
AssertEquals_UINT(Expected := 0, Actual := fbFake.uiPubCount + fbFake.uiPubRejected, Message := 'no birth yet');
fbTel(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 0,
      sTopicPrefix := 'vodokanal/kns1/station', aPoints := aPts);
AssertEquals_UINT(Expected := 0, Actual := fbFake.uiPubCount, Message := 'clock not set: ts would be out of schema');
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 4, Actual := fbFake.uiPubCount, Message := 'published after birth and clock');

coUnit.TEST_FINISHED();
