coUnit.TEST('PublishesAllAfterBirthWithExactJson');

Setup(fbClient := fbFake, aPointTable := aPts);
Run(fbTelemetry := fbTel, fbClient := fbFake, aPointTable := aPts, ltAt := LTIME#1H, xReadyIn := TRUE);
AssertEquals_UINT(Expected := 4, Actual := fbFake.uiPubCount, Message := 'all four metrics');
AssertEquals_UINT(Expected := 0, Actual := fbTel.uiPending, Message := 'nothing pending');
AssertEquals_STRING(
    Expected := '{"schema_version":"1.0","ts":1792137600250,"value":2.35,"quality":"good","unit":"m"}',
    Actual := fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/LT101/level'), Message := 'analog metric JSON');
AssertEquals_STRING(Expected := '{"schema_version":"1.0","ts":1792137600250,"value":0,"quality":"good"}',
    Actual := fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/P101/running'), Message := 'discrete without unit');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/PLC1/uptime', sPart := '"value":5,'),
           Message := 'periodic-only metric in the first publication');
AssertTrue(Condition := fbFake.aPub[1].eQos = E_MqttQos.AtLeastOnce AND fbFake.aPub[1].xRetain,
           Message := 'telemetry: QoS 1 and retain');

coUnit.TEST_FINISHED();
