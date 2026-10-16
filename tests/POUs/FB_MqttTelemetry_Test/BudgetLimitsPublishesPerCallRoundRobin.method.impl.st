coUnit.TEST('BudgetLimitsPublishesPerCallRoundRobin');

fbFake.ForceConnected();
aPts[1].stCfg.sPath := 'D1/m';
aPts[2].stCfg.sPath := 'D2/m';
aPts[3].stCfg.sPath := 'D3/m';
aPts[4].stCfg.sPath := 'D4/m';
aPts[5].stCfg.sPath := 'D5/m';
fbTel(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
      sTopicPrefix := 's/a/u', uiMaxPerCycle := 2, aPoints := aPts);
AssertEquals_UINT(Expected := 2, Actual := fbFake.uiPubCount, Message := 'first call: 2 published');
AssertEquals_UINT(Expected := 3, Actual := fbTel.uiPending, Message := 'first call: 3 pending');
AssertEquals_STRING(Expected := 's/a/u/D2/m', Actual := fbFake.aPub[2].sTopic, Message := 'order');
fbTel(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
      sTopicPrefix := 's/a/u', uiMaxPerCycle := 2, aPoints := aPts);
AssertEquals_STRING(Expected := 's/a/u/D3/m', Actual := fbFake.aPub[3].sTopic, Message := 'second call continues');
fbTel(xEnable := TRUE, xReady := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
      sTopicPrefix := 's/a/u', uiMaxPerCycle := 2, aPoints := aPts);
AssertEquals_UINT(Expected := 5, Actual := fbFake.uiPubCount, Message := 'all published after three calls');
AssertEquals_UINT(Expected := 0, Actual := fbTel.uiPending, Message := 'nothing pending');

coUnit.TEST_FINISHED();
