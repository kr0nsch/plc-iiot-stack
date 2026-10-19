coUnit.TEST('PrgIiotPublishesAndAppliesStationCommand');

IF xRan THEN
    coUnit.TEST_FINISHED();
    RETURN;
END_IF
xRan := TRUE;
stCmdSaved := GVL_Station.stStationCmd;
stStsSaved := GVL_Station.stStationSts;
xK1Saved := GVL_IO.xK1;
fbFake.aCapture[1] := 'vodokanal/kns1/station/PLC1/status/connection';
fbFake.aCapture[2] := 'vodokanal/kns1/station/K1/general_alarm';
fbFake.aCapture[3] := 'vodokanal/kns1/station/KNS1/mode';
fbFake.aCapture[4] := 'vodokanal/kns1/station/LIC101/pv';
fbFake.aCapture[5] := 'vodokanal/kns1/station/KNS1/cmd_ack/SetStepped';
fbFake.aCapture[6] := 'vodokanal/kns1/station/V1/cmd_ack/SetOos';
GVL_IO.xK1 := FALSE;
GVL_Station.stStationSts.eMode := E_StationMode.Auto;
GVL_Iiot.stIiotCfg.xEnable := TRUE;
GVL_Iiot.stIiotCfg.xCommandsEnable := TRUE;
PRG_Iiot.itfClientOverride := fbFake;
FOR iCall := 1 TO 60 DO   // 139 метрик по 8 и 88 тревог по 4 за цикл, с запасом
    PRG_Iiot();
END_FOR
AssertTrue(Condition := GVL_Iiot.stIiotSts.eConnState = E_MqttConnState.Connected AND GVL_Iiot.stIiotSts.xClockValid,
           Message := 'connected with a valid clock');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/PLC1/status/connection',
           sPart := '"node":"PLC1","state":"online","reason":"birth","source":"codesys"'), Message := 'birth');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/K1/general_alarm', sPart := '"value":1,'),
           Message := CONCAT('K1 released -> 1: ',
                             fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/K1/general_alarm')));
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/KNS1/mode', sPart := '"value":1,'),
           Message := CONCAT('station mode Auto -> 1: ',
                             fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/KNS1/mode')));
AssertEquals_UINT(Expected := 1, Actual := fbFake.CountTopic(sTopic := 'vodokanal/kns1/station/LIC101/pv'),
                  Message := 'LIC101 pv published once');
AssertEquals_UINT(Expected := 0, Actual := GVL_Iiot.stIiotSts.uiQueue, Message := 'everything published');

// команда станции SetStepped: шлюз -> GVL_Station.stStationCmd -> обработка станцией -> ответ accepted
SysTimeRtcHighResGet(pTimestamp := uliNow);
sCmd := CONCAT(CONCAT('{"schema_version":"1.1","cmd_id":"kns00001","ts":', ULINT_TO_STRING(uliNow)),
               ',"origin":"test","command":"SetStepped"}');
GVL_Station.stStationCmd.xSetStepped := FALSE;
fbFake.Inject(sTopic := 'vodokanal/kns1/station/KNS1/cmd/SetStepped', sPayload := sCmd, xTruncated := FALSE,
              xRetained := FALSE);
PRG_Iiot();
AssertTrue(Condition := GVL_Station.stStationCmd.xSetStepped,
           Message := 'SetStepped -> GVL_Station.stStationCmd.xSetStepped');
AssertEquals_UINT(Expected := 0,
                  Actual := fbFake.CountTopic(sTopic := 'vodokanal/kns1/station/KNS1/cmd_ack/SetStepped'),
                  Message := 'no ack before the station processed the command');
// станция обработала команду (в тестовом приложении PRG_Station не вызывается — её ответ пишет тест)
GVL_Station.stStationSts.uiCmdSeq := GVL_Station.stStationSts.uiCmdSeq + 1;
GVL_Station.stStationSts.eCmdResult := PL.E_CmdResult.Accepted;
PRG_Iiot();
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/KNS1/cmd_ack/SetStepped',
           sPart := '"cmd_id":"kns00001"'), Message := 'ack for kns00001');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/KNS1/cmd_ack/SetStepped',
           sPart := '"result":"accepted","reason":"ok"}'),
           Message := CONCAT('accepted after the station processed the command: ',
                             fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/KNS1/cmd_ack/SetStepped')));
// SetOos не в белом списке
sCmd := CONCAT(CONCAT('{"schema_version":"1.1","cmd_id":"kns00002","ts":', ULINT_TO_STRING(uliNow)),
               ',"origin":"test","command":"SetOos"}');
fbFake.Inject(sTopic := 'vodokanal/kns1/station/V1/cmd/SetOos', sPayload := sCmd, xTruncated := FALSE,
              xRetained := FALSE);
PRG_Iiot();
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/V1/cmd_ack/SetOos',
           sPart := '"result":"rejected","reason":"not_whitelisted"}'), Message := 'SetOos rejected');
AssertEquals_UDINT(Expected := 1, Actual := GVL_Iiot.stIiotSts.udiCmdAccepted, Message := 'one accepted');

// обмен выключен: штатное отключение; глобальные переменные флагмана — как были
GVL_Iiot.stIiotCfg.xEnable := FALSE;
GVL_Iiot.stIiotCfg.xCommandsEnable := FALSE;
PRG_Iiot();
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/PLC1/status/connection',
           sPart := '"state":"offline","reason":"shutdown"'), Message := 'shutdown status');
PRG_Iiot.itfClientOverride := 0;
PRG_Iiot();
GVL_Station.stStationCmd := stCmdSaved;
GVL_Station.stStationSts := stStsSaved;
GVL_IO.xK1 := xK1Saved;

coUnit.TEST_FINISHED();
