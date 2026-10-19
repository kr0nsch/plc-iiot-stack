coUnit.TEST('StationAlarmIdAndLongSuffix');

fbFake.ForceConnected();
aAlm[1].stCfg.udiId := 100009;
aAlm[1].stCfg.sDevice := 'KNS1';
aAlm[1].stCfg.sSuffix := 'NOAUTO';
aAlm[1].stCfg.uiSlot := 8;
aAlm[1].stCfg.ePriority := E_IiotAlarmPriority.Low;
aAlm[1].stCfg.diWords := 1;
aWords[1].wActive := 16#0100;
aWords[1].wUnack := 16#0100;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
      aAlarms := aAlm, aWords := aWords);
AssertEquals_STRING(Expected := CONCAT('{"schema_version":"1.1","ts":1792137600250,"id":100009,"code":"KNS1.NOAUTO",',
    '"priority":"Low","state":"ActiveUnack","prev_state":"ActiveUnack","reason":"Activated"}'),
    Actual := fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/KNS1/alarm/NOAUTO'),
    Message := 'station alarm JSON');

coUnit.TEST_FINISHED();
