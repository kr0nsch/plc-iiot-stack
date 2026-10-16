xCmdValid := FALSE;
IF NOT xEnable OR itfClient = 0 THEN
    xSubscribed := FALSE;
    xPending := FALSE;
    xAwaitArm := FALSE;
    RETURN;
END_IF
IF NOT itfClient.IsConnected() THEN
    xSubscribed := FALSE;     // после подключения — подписка заново (сессия может быть чистой)
    RETURN;
END_IF
IF NOT xSubscribed THEN
    sFilter := CONCAT(sTopicPrefix, GVL_Const.TOPIC_CMD_FILTER_SUFFIX);
    xSubscribed := itfClient.Subscribe(sTopicFilter := sFilter, eQos := E_MqttQos.AtLeastOnce);
    IF NOT xSubscribed THEN
        RETURN;
    END_IF
END_IF

// Команда прошла проверки в прошлом вызове, но Arm() не вызван: до устройства она не дошла
IF xAwaitArm THEN
    xAwaitArm := FALSE;
    Finish(eReason := E_IiotCmdReason.Timeout, iCmdResult := 0);
END_IF
// Команда в обработке устройством
IF xPending THEN
    IF uiDevSeq <> uiSeqArmed AND iDevResult >= GVL_Const.CMD_RESULT_ACCEPTED
       AND iDevResult <= GVL_Const.CMD_RESULT_LAST THEN
        xPending := FALSE;
        IF iDevResult = GVL_Const.CMD_RESULT_ACCEPTED THEN
            Finish(eReason := E_IiotCmdReason.Ok, iCmdResult := iDevResult);
        ELSE
            Finish(eReason := E_IiotCmdReason.DeviceRejected, iCmdResult := iDevResult);
        END_IF
    ELSIF ltNow < ltPendingSince THEN
        ltPendingSince := ltNow;
    ELSIF (ltNow - ltPendingSince) >= TIME_TO_LTIME(tDeviceTimeout) THEN
        xPending := FALSE;
        Finish(eReason := E_IiotCmdReason.Timeout, iCmdResult := 0);
    END_IF
    IF xPending THEN
        RETURN;
    END_IF
END_IF

FOR uiMsg := 1 TO MAX(uiMaxPerCycle, 1) DO
    IF xCmdValid THEN
        EXIT;
    END_IF
    IF NOT itfClient.Receive(sTopic := sRxTopic, sPayload := sRxPayload, xTruncated => xRxTruncated,
                             xRetained => xRxRetained) THEN
        EXIT;
    END_IF
    udiReceived := udiReceived + 1;
    HandleMessage(aRuleTable := aRules);
END_FOR
