coUnit.TEST('QualityChangeIsImmediate');

Setup(fbClient := fbFake, aPointTable := aPts);
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H, xReadyIn := TRUE);
fbFake.ClearPublished();
aPts[1].eQuality := E_IiotQuality.Bad;
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#100MS, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 1, Actual := fbFake.uiPubCount, Message := 'quality change publishes at once');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/level', sPart := '"quality":"bad"'),
           Message := 'quality bad in JSON');

coUnit.TEST_FINISHED();
