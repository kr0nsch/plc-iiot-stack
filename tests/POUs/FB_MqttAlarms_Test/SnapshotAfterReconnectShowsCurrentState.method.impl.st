coUnit.TEST('SnapshotAfterReconnectShowsCurrentState');

Setup(fbClient := fbFake, aAlarmTable := aAlm);
aWords[1].wActive := 16#0001;
aWords[1].wUnack := 16#0001;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
fbFake.xLinkUp := FALSE;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137630250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
fbFake.xLinkUp := TRUE;
fbFake.ClearPublished();
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137660250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertEquals_UINT(Expected := 3, Actual := fbFake.uiPubCount, Message := 'snapshot again');
AssertEquals_STRING(Expected := CONCAT('{"schema_version":"1.1","ts":1792137600250,"id":110,"code":"P101.FTS",',
    '"priority":"Medium","state":"ActiveUnack","prev_state":"ActiveUnack","reason":"Activated"}'),
    Actual := fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/P101/alarm/FTS'),
    Message := 'current state, the same point as before (original ts)');
AssertEquals_UDINT(Expected := 0, Actual := fbAlm.udiEvents, Message := 'repeat is not an event');

coUnit.TEST_FINISHED();
