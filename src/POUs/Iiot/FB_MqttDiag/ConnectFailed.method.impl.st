diLastError := itfClient.LastError();
IF diLastError = GVL_Const.MQTT_ERR_NONE THEN
    diLastError := diDefaultError;
END_IF
udiConnectFailures := udiConnectFailures + 1;
IF uiConsecutiveFailures < UINT#65535 THEN
    uiConsecutiveFailures := uiConsecutiveFailures + 1;
END_IF
itfClient.Disconnect();
EnterState(eNewState := E_MqttConnState.Backoff);
