FindRule := 0;
FOR diIdx := 1 TO GVL_IiotMap.RULE_COUNT DO
    IF GVL_IiotMap.RULE_CFG[diIdx].sDevice = sDevice AND GVL_IiotMap.RULE_CFG[diIdx].eCommand = eCommand THEN
        FindRule := diIdx;
        RETURN;
    END_IF
END_FOR
