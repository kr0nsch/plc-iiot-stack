// Выключено или нет часов: штатно закрыть связь (offline/shutdown, разрыв в следующем вызове)
IF NOT xEnable OR itfClient = 0 OR NOT F_IiotClockValid(uliTs_ms := uliTs_ms) THEN
    IF itfClient = 0 THEN
        EnterState(eNewState := E_MqttConnState.Disabled);
    ELSIF eState = E_MqttConnState.Connected AND xReady AND_THEN itfClient.IsConnected() THEN
        PublishStatus(xOnline := FALSE, sReason := 'shutdown');
        EnterState(eNewState := E_MqttConnState.Closing);
    ELSIF eState <> E_MqttConnState.Disabled THEN
        itfClient.Disconnect();
        EnterState(eNewState := E_MqttConnState.Disabled);
    END_IF
    IF xEnable AND NOT F_IiotClockValid(uliTs_ms := uliTs_ms) THEN
        diLastError := GVL_Const.MQTT_ERR_NO_CLOCK;
    END_IF
    uiConsecutiveFailures := 0;
    tBackoff := tBackoffMin;
    xConnected := FALSE;
    xReady := FALSE;
    xDegraded := FALSE;
    eNe107 := E_IiotNe107.CheckFunction;
    RETURN;
END_IF
IF tBackoff < tBackoffMin THEN
    tBackoff := tBackoffMin;
END_IF

CASE eState OF
    E_MqttConnState.Disabled, E_MqttConnState.Closing:
        IF eState = E_MqttConnState.Closing THEN
            itfClient.Disconnect();
        END_IF
        StartConnect(stBrokerCfg := stBroker);

    E_MqttConnState.Connecting:
        IF NOT itfClient.IsConnected() AND_THEN InState() >= TIME_TO_LTIME(tConnectTimeout) THEN
            ConnectFailed(diDefaultError := GVL_Const.MQTT_ERR_CONNECT_TIMEOUT);
        END_IF

    E_MqttConnState.Connected:
        IF NOT itfClient.IsConnected() THEN
            udiDisconnects := udiDisconnects + 1;
            diLastError := itfClient.LastError();
            IF diLastError = GVL_Const.MQTT_ERR_NONE THEN
                diLastError := GVL_Const.MQTT_ERR_CONNECTION_LOST;
            END_IF
            itfClient.Disconnect();
            xReady := FALSE;
            EnterState(eNewState := E_MqttConnState.Backoff);
        ELSIF InState() >= TIME_TO_LTIME(tStable) THEN
            // связь устойчива: следующая потеря — с минимальной паузы
            tBackoff := tBackoffMin;
            uiConsecutiveFailures := 0;
        END_IF

    E_MqttConnState.Backoff:
        IF InState() >= TIME_TO_LTIME(tBackoff) THEN
            // пауза для следующей неудачи — вдвое больше, не больше tBackoffMax
            IF tBackoff >= tBackoffMax / 2 THEN
                tBackoff := tBackoffMax;
            ELSE
                tBackoff := tBackoff * 2;
            END_IF
            StartConnect(stBrokerCfg := stBroker);
        END_IF
END_CASE

// подключение могло состояться в этом же вызове
IF eState = E_MqttConnState.Connecting AND_THEN itfClient.IsConnected() THEN
    udiConnects := udiConnects + 1;
    EnterState(eNewState := E_MqttConnState.Connected);
    xReady := FALSE;
    xDegraded := FALSE;
    ltDegradeStart := ltNow;
    udiPubFailedRef := udiPubFailed;
END_IF
xConnected := eState = E_MqttConnState.Connected;

// рождение узла, затем можно публиковать
IF xConnected AND NOT xReady THEN
    xReady := PublishStatus(xOnline := TRUE, sReason := 'birth');
END_IF
// отказы публикаций за окно
IF xConnected THEN
    IF ltNow < ltDegradeStart THEN
        ltDegradeStart := ltNow;
    ELSIF (ltNow - ltDegradeStart) >= TIME_TO_LTIME(tDegradeWindow) THEN
        ltDegradeStart := ltNow;
        xDegraded := udiPubFailed <> udiPubFailedRef;
        udiPubFailedRef := udiPubFailed;
    END_IF
END_IF
UpdateNe107();
