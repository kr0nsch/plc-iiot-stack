coUnit.TEST('ChangeWhileOfflineIsEventAfterReconnect');

Setup(fbClient := fbFake, aAlarmTable := aAlm);
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600000,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
fbFake.xLinkUp := FALSE;
aWords[1].wActive := 16#0001;
aWords[1].wUnack := 16#0001;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137610000,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertEquals_UDINT(Expected := 0, Actual := fbAlm.udiEvents, Message := 'nothing published offline');
fbFake.xLinkUp := TRUE;
fbFake.ClearPublished();
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137665000,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertEquals_STRING(Expected := CONCAT('{"schema_version":"1.0","ts":1792137665000,"id":110,"code":"P101.FTS",',
    '"priority":"Medium","state":"ActiveUnack","prev_state":"Normal","reason":"Activated"}'),
    Actual := fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/P101/alarm/FTS'),
    Message := 'activation missed offline: event with the current ts');
AssertEquals_UDINT(Expected := 1, Actual := fbAlm.udiEvents, Message := 'one event');

coUnit.TEST_FINISHED();
