coUnit.TEST('WordsOutOfTableMeanNormal');

Setup(fbClient := fbFake, aAlarmTable := aAlm);
aAlm[1].stCfg.diWords := 5;
aWords[1].wActive := 16#0001;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertTrue(Condition := aAlm[1].eState = E_IiotAlarmState.Normal, Message := 'out of table is normal');

coUnit.TEST_FINISHED();
