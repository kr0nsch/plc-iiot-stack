// Состояние каждой тревоги — каждый вызов (видно и без связи)
UpdateStates(aAlarmTable := aAlarms, aWordTable := aWords);

IF NOT xEnable OR NOT xReady OR itfClient = 0 OR NOT F_IiotClockValid(uliTs_ms := uliTs_ms) THEN
    ResetSent(aAlarmTable := aAlarms);
    RETURN;
END_IF
IF NOT itfClient.IsConnected() THEN
    ResetSent(aAlarmTable := aAlarms);
    RETURN;
END_IF
PublishDue(aAlarmTable := aAlarms);
