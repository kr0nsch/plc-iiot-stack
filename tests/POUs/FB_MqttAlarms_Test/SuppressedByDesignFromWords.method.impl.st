coUnit.TEST('SuppressedByDesignFromWords');

Setup(fbClient := fbFake, aAlarmTable := aAlm);
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
aWords[2].wSuppressed := 16#0001;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/alarm/HH',
           sPart := '"state":"SuppressedByDesign","prev_state":"Normal","reason":"Suppressed"'),
           Message := 'suppressed');
aWords[2].wSuppressed := 0;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/alarm/HH',
           sPart := '"state":"Normal","prev_state":"SuppressedByDesign","reason":"Unsuppressed"'),
           Message := 'unsuppressed');

coUnit.TEST_FINISHED();
