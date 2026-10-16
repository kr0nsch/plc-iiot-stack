IF LEN(stCfg.sUser) > 0 OR LEN(stCfg.sPassword) > 0 THEN
    diError := MQTT_ERR_AUTH_UNSUPPORTED;
    RETURN;
END_IF
sUrl := CONCAT(CONCAT(stCfg.sHost, ':'), UINT_TO_STRING(stCfg.uiPort));
stInOut.ClientID := stCfg.sClientId;
xTls := stCfg.xTls;
diError := GVL_Const.MQTT_ERR_NONE;
xEnable := TRUE;
Connect := TRUE;
