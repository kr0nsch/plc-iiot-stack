FindRule := LOWER_BOUND(aRuleTable, 1) - 1;
FOR diIdx := LOWER_BOUND(aRuleTable, 1) TO UPPER_BOUND(aRuleTable, 1) DO
    IF aRuleTable[diIdx].eCommand = eCommandIn AND aRuleTable[diIdx].sDevice = sTopicDevice THEN
        FindRule := diIdx;
        RETURN;
    END_IF
END_FOR
