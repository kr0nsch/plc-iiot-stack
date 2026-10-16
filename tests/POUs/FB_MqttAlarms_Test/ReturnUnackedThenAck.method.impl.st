coUnit.TEST('ReturnUnackedThenAck');

Setup(fbClient := fbFake, aAlarmTable := aAlm);
aWords[2].wActive := 16#0001;
aWords[2].wUnack := 16#0001;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
aWords[2].wActive := 0;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/alarm/HH',
           sPart := '"state":"RtnUnack","prev_state":"ActiveUnack","reason":"Cleared"'), Message := 'return unacked');
aWords[2].wUnack := 0;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/alarm/HH',
           sPart := '"state":"Normal","prev_state":"RtnUnack","reason":"Acked"'), Message := 'acked after return');

coUnit.TEST_FINISHED();
