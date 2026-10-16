// Строка белого списка для (sTopicDevice, eCommandIn); нет — LOWER_BOUND - 1.
METHOD PRIVATE FindRule : DINT
VAR_IN_OUT
    aRuleTable : ARRAY[*] OF ST_IiotCmdRule;
END_VAR
VAR_INPUT
    eCommandIn : E_IiotCommand;
END_VAR
VAR
    diIdx : DINT;
END_VAR
