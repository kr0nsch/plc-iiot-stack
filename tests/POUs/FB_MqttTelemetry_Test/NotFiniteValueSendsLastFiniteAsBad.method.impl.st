coUnit.TEST('NotFiniteValueSendsLastFiniteAsBad');

Setup(fbClient := fbFake, aPointTable := aPts);
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H, xReadyIn := TRUE);
pBits := ADR(lwNan);
aPts[1].lrValue := pBits^;
fbFake.ClearPublished();
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#2S, xReadyIn := TRUE);
AssertEquals_STRING(Expected := '{"schema_version":"1.0","ts":1792137600250,"value":2.35,"quality":"bad","unit":"m"}',
    Actual := fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/LT101/level'),
    Message := 'NaN: last finite value, quality bad');
aPts[1].lrValue := 2.5;
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H + LTIME#4S, xReadyIn := TRUE);
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/level',
           sPart := '"value":2.5,"quality":"good"'), Message := 'finite again: value and quality restored');

coUnit.TEST_FINISHED();
