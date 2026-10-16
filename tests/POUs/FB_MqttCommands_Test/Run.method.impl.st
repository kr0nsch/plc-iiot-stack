IF LEN(sTopic) > 0 THEN
    fbClient.Inject(sTopic := sTopic, sPayload := sPayload, xTruncated := FALSE, xRetained := xRetainedIn);
END_IF
fbCommands(xEnable := TRUE, itfClient := fbClient, ltNow := ltAt, uliTs_ms := uliNow_ms,
           sTopicPrefix := 'vodokanal/kns1/station', uiDevSeq := uiSeq, iDevResult := iResult, aRules := aRuleTable);
