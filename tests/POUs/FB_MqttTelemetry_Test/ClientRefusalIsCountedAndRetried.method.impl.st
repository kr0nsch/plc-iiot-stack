coUnit.TEST('ClientRefusalIsCountedAndRetried');

Setup(fbClient := fbFake, aPointTable := aPts);
fbFake.xPublishAccepts := FALSE;
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H, xReadyIn := TRUE);
AssertEquals_UDINT(Expected := 1, Actual := fbTel.udiFailed, Message := 'one refusal stops publishing in this call');
AssertEquals_UINT(Expected := 4, Actual := fbTel.uiPending, Message := 'all metrics pending');
fbFake.xPublishAccepts := TRUE;
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 4, Actual := fbFake.uiPubCount, Message := 'published after the queue frees');

coUnit.TEST_FINISHED();
