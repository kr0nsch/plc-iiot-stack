coUnit.TEST('NegativeAndLargeValues');

Setup(fbClient := fbFake, aPointTable := aPts);
aPts[1].lrValue := -3.25;
aPts[3].lrValue := 4294967295.0;
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H, xReadyIn := TRUE);
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/level', sPart := '"value":-3.25,'),
           Message := 'negative analog');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/starts', sPart := '"value":4294967295,'),
           Message := 'UDINT maximum as integer');

coUnit.TEST_FINISHED();
