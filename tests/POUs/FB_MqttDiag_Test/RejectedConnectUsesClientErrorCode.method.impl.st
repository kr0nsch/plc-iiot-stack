coUnit.TEST('RejectedConnectUsesClientErrorCode');

fbFake.xConnectAccepts := FALSE;
fbFake.diError := 5;
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertEquals_DINT(Expected := 5, Actual := fbDiag.diLastError, Message := 'client error code');
fbFake.diError := 0;
fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H + LTIME#1S, uliTs_ms := 1792137600250,
    sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertEquals_DINT(Expected := GVL_Const.MQTT_ERR_CONNECT_REJECTED, Actual := fbDiag.diLastError,
    Message := 'default code');

coUnit.TEST_FINISHED();
