coUnit.TEST('ReconnectRepeatsLastEventWithItsTs');

Setup(fbClient := fbFake, aAlarmTable := aAlm);
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600000,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
aWords[1].wActive := 16#0001;
aWords[1].wUnack := 16#0001;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137605000,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertEquals_UDINT(Expected := 1, Actual := fbAlm.udiEvents, Message := 'activated once');
fbFake.xLinkUp := FALSE;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137610000,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
fbFake.xLinkUp := TRUE;
fbFake.ClearPublished();
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137665000,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertEquals_UINT(Expected := 3, Actual := fbFake.uiPubCount, Message := 'all alarms after reconnect');
AssertEquals_STRING(Expected := CONCAT('{"schema_version":"1.0","ts":1792137605000,"id":110,"code":"P101.FTS",',
    '"priority":"Medium","state":"ActiveUnack","prev_state":"Normal","reason":"Activated"}'),
    Actual := fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/P101/alarm/FTS'),
    Message := 'the Activated event repeated as is');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/alarm/HH',
           sPart := '"ts":1792137600000,'), Message := 'unchanged alarm: snapshot repeated with its ts');
AssertEquals_UDINT(Expected := 1, Actual := fbAlm.udiEvents, Message := 'no new events after reconnect');

coUnit.TEST_FINISHED();
