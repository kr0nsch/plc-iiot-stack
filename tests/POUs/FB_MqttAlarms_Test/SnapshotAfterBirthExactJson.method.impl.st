coUnit.TEST('SnapshotAfterBirthExactJson');

Setup(fbClient := fbFake, aAlarmTable := aAlm);
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertEquals_UINT(Expected := 3, Actual := fbFake.uiPubCount, Message := 'snapshot of all alarms');
AssertEquals_STRING(Expected := CONCAT('{"schema_version":"1.1","ts":1792137600250,"id":110,"code":"P101.FTS",',
    '"priority":"Medium","state":"Normal","prev_state":"Normal","reason":"Cleared"}'),
    Actual := fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/P101/alarm/FTS'), Message := 'snapshot JSON');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/alarm/HH', sPart := '"id":1010,'),
           Message := 'LT101.HH snapshot');
AssertTrue(Condition := fbFake.aPub[1].eQos = E_MqttQos.AtLeastOnce AND fbFake.aPub[1].xRetain,
           Message := 'alarms: QoS 1 and retain');
AssertEquals_UDINT(Expected := 0, Actual := fbAlm.udiEvents, Message := 'snapshot is not an event');

coUnit.TEST_FINISHED();
