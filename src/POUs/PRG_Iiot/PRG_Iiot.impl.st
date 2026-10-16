// 0. Таблицы настроек из схемы данных — один раз
ltNow := F_IiotNow();
IF NOT xInitDone THEN
    FOR diIdx := 1 TO GVL_IiotMap.POINT_COUNT DO
        aPoints[diIdx].stCfg := GVL_IiotMap.POINT_CFG[diIdx];
    END_FOR
    FOR diIdx := 1 TO GVL_IiotMap.ALARM_COUNT DO
        aAlarms[diIdx].stCfg := GVL_IiotMap.ALARM_CFG[diIdx];
    END_FOR
    FOR diIdx := 1 TO GVL_IiotMap.RULE_COUNT DO
        aRules[diIdx] := GVL_IiotMap.RULE_CFG[diIdx];
    END_FOR
    ltStart := ltNow;
    xInitDone := TRUE;
END_IF

// 1. Клиент MQTT: адаптер библиотеки (или подменный клиент тестов) либо клиент без транспорта
IF itfClientOverride <> 0 THEN
    itfClient := itfClientOverride;
ELSE
    itfClient := fbClientNone;
END_IF
itfClient.Cycle();

// 2. Время: монотонное — для таймаутов и периодов, календарное (UTC, мс) — для ts и проверки команд
xClockValid := SysTimeRtcHighResGet(pTimestamp := uliTs_ms) = RTC_OK AND F_IiotClockValid(uliTs_ms := uliTs_ms);
sPrefix := CONCAT(CONCAT(GVL_Iiot.stIiotCfg.sSite, GVL_Const.TOPIC_SEPARATOR), GVL_Iiot.stIiotCfg.sArea);
sPrefix := CONCAT(CONCAT(sPrefix, GVL_Const.TOPIC_SEPARATOR), GVL_Iiot.stIiotCfg.sUnit);

// 3. Значения флагмана -> метрики и слова тревог; метрики узла
fbMap.FillPoints(aPointTable := aPoints);
fbMap.FillAlarmWords(aWordTable := aAlarmWords);
FillNodePoints();

// 4. Связь и состояние узла
fbDiag(xEnable := GVL_Iiot.stIiotCfg.xEnable,
       itfClient := itfClient,
       ltNow := ltNow,
       uliTs_ms := uliTs_ms,
       sTopicPrefix := sPrefix,
       sNode := GVL_Iiot.stIiotCfg.sNode,
       sSwVersion := GVL_Iiot.stIiotCfg.sSwVersion,
       tPeriod := GVL_Iiot.stIiotCfg.tTelemetryPeriod,
       udiPubFailed := fbTelemetry.udiFailed + fbAlarms.udiFailed,
       stBroker := GVL_Iiot.stIiotCfg.stBroker);

// 5. Телеметрия и тревоги — после рождения узла
fbTelemetry(xEnable := GVL_Iiot.stIiotCfg.xEnable,
            xReady := fbDiag.xReady,
            itfClient := itfClient,
            ltNow := ltNow,
            uliTs_ms := uliTs_ms,
            sTopicPrefix := sPrefix,
            tPeriod := GVL_Iiot.stIiotCfg.tTelemetryPeriod,
            aPoints := aPoints);
fbAlarms(xEnable := GVL_Iiot.stIiotCfg.xEnable,
         xReady := fbDiag.xReady,
         itfClient := itfClient,
         uliTs_ms := uliTs_ms,
         sTopicPrefix := sPrefix,
         aAlarms := aAlarms,
         aWords := aAlarmWords);

// 6. Команды: состояние устройства команды в обработке, приём, запись в GVL_Hmi
IF fbCommands.xPending THEN
    fbMap.DeviceCmdState(diDev := RuleDevice(diRule := fbCommands.stCmd.diRule), uiSeq => uiDevSeq,
                         iResult => iDevResult);
END_IF
fbCommands(xEnable := GVL_Iiot.stIiotCfg.xEnable AND GVL_Iiot.stIiotCfg.xCommandsEnable,
           itfClient := itfClient,
           ltNow := ltNow,
           uliTs_ms := uliTs_ms,
           sTopicPrefix := sPrefix,
           uiDevSeq := uiDevSeq,
           iDevResult := iDevResult,
           aRules := aRules);
IF fbCommands.xCmdValid THEN
    fbMap.DeviceCmdState(diDev := RuleDevice(diRule := fbCommands.stCmd.diRule), uiSeq => uiDevSeq,
                         iResult => iDevResult);
    fbMap.ApplyCommand(diRule := fbCommands.stCmd.diRule, rValue := fbCommands.stCmd.rValue);
    fbCommands.Arm(uiSeqBefore := uiDevSeq);
END_IF

// 7. Состояние для HMI и SCADA
GVL_Iiot.stIiotSts.eConnState := fbDiag.eState;
GVL_Iiot.stIiotSts.eNe107 := fbDiag.eNe107;
GVL_Iiot.stIiotSts.udiConnects := fbDiag.udiConnects;
GVL_Iiot.stIiotSts.udiDisconnects := fbDiag.udiDisconnects;
GVL_Iiot.stIiotSts.udiConnectFailures := fbDiag.udiConnectFailures;
GVL_Iiot.stIiotSts.diLastError := fbDiag.diLastError;
GVL_Iiot.stIiotSts.udiPublished := fbTelemetry.udiPublished + fbAlarms.udiPublished;
GVL_Iiot.stIiotSts.udiPublishFailed := fbTelemetry.udiFailed + fbAlarms.udiFailed;
GVL_Iiot.stIiotSts.uiQueue := fbTelemetry.uiPending + fbAlarms.uiPending;
GVL_Iiot.stIiotSts.udiDropped := fbTelemetry.udiDropped + fbAlarms.udiDropped + fbCommands.udiAckFailed;
GVL_Iiot.stIiotSts.udiCmdAccepted := fbCommands.udiAccepted;
GVL_Iiot.stIiotSts.udiCmdRejected := fbCommands.udiRejected + fbCommands.udiDropped;
GVL_Iiot.stIiotSts.eLastCmdReason := fbCommands.eLastReason;
GVL_Iiot.stIiotSts.xClockValid := xClockValid;
