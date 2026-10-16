coUnit.TEST('IntegerAnyChangeAndPeriodicOnly');

Setup(fbClient := fbFake, aPointTable := aPts);
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H, xReadyIn := TRUE);
fbFake.ClearPublished();
aPts[2].lrValue := 1.0;
aPts[3].lrValue := 8.0;
aPts[4].lrValue := 7.0;
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#2S, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 2, Actual := fbFake.uiPubCount, Message := 'running and starts, not uptime');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/starts', sPart := '"value":8,'),
           Message := 'starts 8');
AssertEquals_UINT(Expected := 0, Actual := fbFake.CountTopic(sTopic := 'vodokanal/kns1/station/PLC1/uptime'),
                  Message := 'uptime waits for the period');
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#10S, xReadyIn := TRUE);
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/PLC1/uptime', sPart := '"value":7,'),
           Message := 'uptime with the period');

coUnit.TEST_FINISHED();
