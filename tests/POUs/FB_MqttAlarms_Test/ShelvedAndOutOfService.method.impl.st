coUnit.TEST('ShelvedAndOutOfService');

Setup(fbClient := fbFake, aAlarmTable := aAlm);
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
aWords[1].wShelved := 16#0004;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/alarm/FTP',
           sPart := '"state":"Shelved","prev_state":"Normal","reason":"Shelved"'), Message := 'shelved');
aWords[1].wShelved := 0;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/alarm/FTP',
           sPart := '"state":"Normal","prev_state":"Shelved","reason":"Unshelved"'), Message := 'unshelved');
fbFake.ClearPublished();
aWords[1].xOutOfService := TRUE;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertEquals_UINT(Expected := 2, Actual := fbFake.uiPubCount, Message := 'both alarms of the device');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/alarm/FTS',
    sPart := '"state":"OutOfService","prev_state":"Normal","reason":"OosOn"'),
           Message := 'out of service');

coUnit.TEST_FINISHED();
