// Поставить сообщение в очередь (sTopic пусто — без сообщения) и вызвать FB_MqttCommands.
METHOD PRIVATE Run
VAR_IN_OUT
    fbClient : FB_MqttClientFake;
    fbCommands : FB_MqttCommands;
    aRuleTable : ARRAY[*] OF ST_IiotCmdRule;
END_VAR
VAR_INPUT
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN) := '';
    sPayload : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN) := '';
    xRetainedIn : BOOL := FALSE;
    ltAt : LTIME := LTIME#1H;
    uliNow_ms : ULINT := 1792137600250;
    uiSeq : UINT := 0;
    iResult : INT := 0;
END_VAR
