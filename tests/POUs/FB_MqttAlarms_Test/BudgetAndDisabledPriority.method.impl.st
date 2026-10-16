coUnit.TEST('BudgetAndDisabledPriority');

Setup(fbClient := fbFake, aAlarmTable := aAlm);
aAlm[2].stCfg.ePriority := E_IiotAlarmPriority.None;
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station', uiMaxPerCycle := 1,
      aAlarms := aAlm, aWords := aWords);
AssertEquals_UINT(Expected := 1, Actual := fbFake.uiPubCount, Message := 'one per call');
AssertEquals_UINT(Expected := 2, Actual := fbAlm.uiPending, Message := 'two pending');
fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station', uiMaxPerCycle := 1,
      aAlarms := aAlm, aWords := aWords);fbAlm(xEnable := TRUE, xReady := TRUE, itfClient := fbFake,
          uliTs_ms := 1792137600250, sTopicPrefix := 'vodokanal/kns1/station', uiMaxPerCycle := 1,
      aAlarms := aAlm, aWords := aWords);
AssertEquals_UINT(Expected := 2, Actual := fbFake.uiPubCount, Message := 'priority None not published');
AssertEquals_UDINT(Expected := 1, Actual := fbAlm.udiDropped, Message := 'priority None counted as dropped');
AssertEquals_UINT(Expected := 0, Actual := fbAlm.uiPending, Message := 'nothing pending');

coUnit.TEST_FINISHED();
