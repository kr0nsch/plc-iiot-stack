uliTs := uliTs_ms;
IF stAlarm.xSent OR (stAlarm.uliEventTs_ms > 0 AND stAlarm.eState <> stAlarm.eLastState) THEN
    xEvent := TRUE;                     // событие: в том числе переход, случившийся без связи
    ePrev := stAlarm.eLastState;
ELSIF stAlarm.uliEventTs_ms > 0 THEN
    xEvent := FALSE;                    // повтор последней публикации после переподключения
    ePrev := stAlarm.eEventPrev;
    uliTs := stAlarm.uliEventTs_ms;
ELSE
    xEvent := FALSE;                    // снимок: с запуска ПЛК не публиковалась
    ePrev := stAlarm.eState;
END_IF
sPriority := F_IiotAlarmPriorityText(ePriority := stAlarm.stCfg.ePriority);
sCode := CONCAT(CONCAT(stAlarm.stCfg.sDevice, '.'), stAlarm.stCfg.sSuffix);
sPath := CONCAT(CONCAT(stAlarm.stCfg.sDevice, GVL_Const.TOPIC_SEPARATOR), GVL_Const.TOPIC_ALARM_LEVEL);
sPath := CONCAT(CONCAT(sPath, GVL_Const.TOPIC_SEPARATOR), stAlarm.stCfg.sSuffix);
sTopic := F_IiotTopic(sPrefix := sTopicPrefix, sPath := sPath);
fbJson.Begin();
fbJson.AddString(sKey := 'schema_version', sValue := GVL_Const.IIOT_SCHEMA_VERSION);
fbJson.AddInt(sKey := 'ts', liValue := ULINT_TO_LINT(uliTs));
fbJson.AddInt(sKey := 'id', liValue := UDINT_TO_LINT(stAlarm.stCfg.udiId));
fbJson.AddString(sKey := 'code', sValue := sCode);
fbJson.AddString(sKey := 'priority', sValue := sPriority);
fbJson.AddString(sKey := 'state', sValue := F_IiotAlarmStateText(eState := stAlarm.eState));
fbJson.AddString(sKey := 'prev_state', sValue := F_IiotAlarmStateText(eState := ePrev));
fbJson.AddString(sKey := 'reason',
                 sValue := F_IiotAlarmReasonText(eReason := F_IiotAlarmReason(ePrev := ePrev, eNew := stAlarm.eState)));

IF NOT fbJson.Finish() OR LEN(sTopic) = 0 OR LEN(sPriority) = 0 THEN
    udiDropped := udiDropped + 1;
ELSIF itfClient.Publish(sTopic := sTopic, eQos := E_MqttQos.AtLeastOnce, xRetain := TRUE,
                        sPayload := fbJson.sJson) THEN
    udiPublished := udiPublished + 1;
    IF xEvent THEN
        udiEvents := udiEvents + 1;
    END_IF
ELSE
    udiFailed := udiFailed + 1;
    RETURN;
END_IF
stAlarm.eLastState := stAlarm.eState;
stAlarm.eEventPrev := ePrev;
stAlarm.uliEventTs_ms := uliTs;
stAlarm.xSent := TRUE;
PublishAlarm := TRUE;
