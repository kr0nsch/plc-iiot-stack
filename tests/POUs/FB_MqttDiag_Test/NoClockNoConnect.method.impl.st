coUnit.TEST('NoClockNoConnect');

fbDiag(xEnable := TRUE, itfClient := fbFake, ltNow := LTIME#1H, uliTs_ms := 0, sTopicPrefix := 'vodokanal/kns1/station',
       stBroker := stCfg);

AssertEquals_UINT(Expected := 0, Actual := fbFake.uiConnectCalls, Message := 'no connect without clock');
AssertEquals_DINT(Expected := GVL_Const.MQTT_ERR_NO_CLOCK, Actual := fbDiag.diLastError, Message := 'no clock code');
AssertTrue(Condition := fbDiag.eNe107 = E_IiotNe107.CheckFunction, Message := 'NE107 C');

coUnit.TEST_FINISHED();
