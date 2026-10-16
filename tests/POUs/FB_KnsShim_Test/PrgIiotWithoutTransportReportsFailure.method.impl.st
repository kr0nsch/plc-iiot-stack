coUnit.TEST('PrgIiotWithoutTransportReportsFailure');

GVL_Iiot.stIiotCfg.xEnable := TRUE;
PRG_Iiot.itfClientOverride := 0;
PRG_Iiot();
AssertTrue(Condition := GVL_Iiot.stIiotSts.eConnState = E_MqttConnState.Backoff,
    Message := 'backoff without transport');
AssertEquals_DINT(Expected := GVL_Const.MQTT_ERR_NO_TRANSPORT, Actual := GVL_Iiot.stIiotSts.diLastError,
                  Message := 'no transport code');
GVL_Iiot.stIiotCfg.xEnable := FALSE;
PRG_Iiot();

coUnit.TEST_FINISHED();
