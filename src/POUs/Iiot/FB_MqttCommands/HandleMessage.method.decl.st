// Разбор принятого сообщения: без ответа (чужой топик, нет cmd_id), отказ с ответом или команда в stCmd.
METHOD PRIVATE HandleMessage
VAR_IN_OUT
    aRuleTable : ARRAY[*] OF ST_IiotCmdRule;
END_VAR
VAR
    eReason : E_IiotCmdReason;
END_VAR
