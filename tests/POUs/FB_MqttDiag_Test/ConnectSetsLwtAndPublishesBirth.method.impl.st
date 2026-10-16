coUnit.TEST('ConnectSetsLwtAndPublishesBirth');

fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertTrue(Condition := fbDiag.eState = E_MqttConnState.Connected, Message := 'connected in the same call');
AssertTrue(Condition := fbDiag.xReady AND fbDiag.eNe107 = E_IiotNe107.Good, Message := 'ready, NE107 Good');
AssertEquals_STRING(Expected := 'vodokanal/kns1/station/PLC1/status/connection', Actual := fbFake.stLastCfg.sWillTopic,
    Message := 'LWT topic');
AssertEquals_STRING(
    Expected := '{"schema_version":"1.0","ts":1792137600250,"node":"PLC1","state":"offline","reason":"lwt"}',
    Actual := fbFake.stLastCfg.sWillPayload, Message := 'LWT payload');
AssertTrue(Condition := fbFake.stLastCfg.xWillRetain, Message := 'LWT retained');
AssertEquals_STRING(Expected := CONCAT('{"schema_version":"1.0","ts":1792137600250,"node":"PLC1","state":"online",',
    '"reason":"birth","source":"codesys","sw_version":"0.1.0","period_ms":60000}'),
    Actual := fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/PLC1/status/connection'),
        Message := 'birth payload');
uiIdx := fbFake.FindLast(sTopic := 'vodokanal/kns1/station/PLC1/status/connection');
AssertTrue(Condition := uiIdx > 0, Message := 'birth published');
IF uiIdx > 0 THEN
    AssertTrue(Condition := fbFake.aPub[uiIdx].xRetain AND fbFake.aPub[uiIdx].eQos = E_MqttQos.AtLeastOnce,
               Message := 'birth: QoS 1, retain');
END_IF

coUnit.TEST_FINISHED();
