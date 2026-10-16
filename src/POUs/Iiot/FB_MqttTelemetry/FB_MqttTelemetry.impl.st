// Нет связи или рождения: после него всё публикуется заново
IF NOT xEnable OR NOT xReady OR itfClient = 0 OR NOT F_IiotClockValid(uliTs_ms := uliTs_ms) THEN
    ResetSent(aPointTable := aPoints);
    RETURN;
END_IF
IF NOT itfClient.IsConnected() THEN
    ResetSent(aPointTable := aPoints);
    RETURN;
END_IF

// Контрольная публикация: все метрики принудительно
IF NOT xPeriodRunning OR ltNow < ltPeriodStart THEN
    xPeriodRunning := TRUE;
    ltPeriodStart := ltNow;
ELSIF tPeriod > T#0S AND_THEN (ltNow - ltPeriodStart) >= TIME_TO_LTIME(tPeriod) THEN
    ltPeriodStart := ltNow;
    ForceAll(aPointTable := aPoints);
END_IF

PublishDue(aPointTable := aPoints);
