wBit := SHL(SLOT0_MASK, uiSlot);
IF stWords.xOutOfService THEN
    F_IiotAlarmStateOf := E_IiotAlarmState.OutOfService;
ELSIF (stWords.wShelved AND wBit) <> 0 THEN
    F_IiotAlarmStateOf := E_IiotAlarmState.Shelved;
ELSIF (stWords.wActive AND wBit) <> 0 AND (stWords.wUnack AND wBit) <> 0 THEN
    F_IiotAlarmStateOf := E_IiotAlarmState.ActiveUnack;
ELSIF (stWords.wActive AND wBit) <> 0 THEN
    F_IiotAlarmStateOf := E_IiotAlarmState.ActiveAck;
ELSIF (stWords.wUnack AND wBit) <> 0 THEN
    F_IiotAlarmStateOf := E_IiotAlarmState.RtnUnack;
ELSE
    F_IiotAlarmStateOf := E_IiotAlarmState.Normal;
END_IF
