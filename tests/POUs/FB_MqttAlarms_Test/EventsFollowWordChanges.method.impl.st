coUnit.TEST('EventsFollowWordChanges');

Setup(fbClient := fbFake, aAlarmTable := aAlm);
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
fbFake.ClearPublished();
aWords[1].wActive := 16#0001;
aWords[1].wUnack := 16#0001;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertEquals_UINT(Expected := 1, Actual := fbFake.uiPubCount, Message := 'one event');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/alarm/FTS',
           sPart := '"state":"ActiveUnack","prev_state":"Normal","reason":"Activated"'), Message := 'activated');
aWords[1].wUnack := 0;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/alarm/FTS',
           sPart := '"state":"ActiveAck","prev_state":"ActiveUnack","reason":"Acked"'), Message := 'acked');
aWords[1].wActive := 0;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/alarm/FTS',
           sPart := '"state":"Normal","prev_state":"ActiveAck","reason":"Cleared"'), Message := 'cleared');
AssertEquals_UDINT(Expected := 3, Actual := fbAlm.udiEvents, Message := 'three events');
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertEquals_UINT(Expected := 3, Actual := fbFake.uiPubCount, Message := 'no event without change');

coUnit.TEST_FINISHED();
