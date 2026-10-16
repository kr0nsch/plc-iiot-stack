coUnit.TEST('PrgIiotPublishesFlagshipTagsAndAppliesCommands');

IF xRan THEN
    coUnit.TEST_FINISHED();
    RETURN;
END_IF
xRan := TRUE;
fbFake.aCapture[1] := 'vodokanal/kns1/station/PLC1/status/connection';
fbFake.aCapture[2] := 'vodokanal/kns1/station/LT101/level';
fbFake.aCapture[3] := 'vodokanal/kns1/station/P101/running';
fbFake.aCapture[4] := 'vodokanal/kns1/station/P101/state';
fbFake.aCapture[5] := 'vodokanal/kns1/station/YS405/fire';
fbFake.aCapture[6] := 'vodokanal/kns1/station/LT101/alarm/HH';
fbFake.aCapture[7] := 'vodokanal/kns1/station/P101/cmd_ack/Start';
fbFake.aCapture[8] := 'vodokanal/kns1/station/V1/cmd_ack/SetOos';
// значения флагмана (в заглушках их пишет тест)
GVL_Devices.fbLT101.stSts.rValue_eu := 2.5;
GVL_Devices.fbLT101.xValid := TRUE;
GVL_Devices.fbLT101.stSts.stCommon.eNe107 := E_Ne107Status.Good;
GVL_Devices.fbLT101.stSts.stCommon.wAlmActive := 16#0001;
GVL_Devices.fbLT101.stSts.stCommon.wAlmUnack := 16#0001;
GVL_Devices.fbP101.xRunning := TRUE;
GVL_Devices.fbP101.stSts.eState := E_MotorState.Running;
GVL_Devices.fbP101.stSts.stCommon.eNe107 := E_Ne107Status.Good;
GVL_Devices.fbP101.stSts.stCommon.eMode := E_DeviceMode.Auto;
GVL_Iiot.stIiotCfg.xEnable := TRUE;
GVL_Iiot.stIiotCfg.xCommandsEnable := TRUE;
PRG_Iiot.itfClientOverride := fbFake;
FOR iCall := 1 TO 30 DO
    PRG_Iiot();
END_FOR
AssertTrue(Condition := GVL_Iiot.stIiotSts.eConnState = E_MqttConnState.Connected AND GVL_Iiot.stIiotSts.xClockValid,
           Message := 'connected with a valid clock');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/PLC1/status/connection',
           sPart := '"node":"PLC1","state":"online","reason":"birth","source":"codesys"'), Message := 'birth');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/level',
           sPart := '"value":2.5,"quality":"good","unit":"m"}'),
           Message := CONCAT('LT101 level: ', fbFake.LastPayload(sTopic := 'vodokanal/kns1/station/LT101/level')));
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/running', sPart := '"value":1,'),
           Message := 'P101 running as 1');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/state', sPart := '"value":2,'),
           Message := 'P101 state Running = 2');
// заглушка YS405 не вызывалась: eNe107 = CheckFunction (значение по умолчанию ST_DeviceSts) — uncertain
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/YS405/fire', sPart := '"quality":"uncertain"'),
           Message := 'device in CheckFunction published as uncertain');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/LT101/alarm/HH',
           sPart := '"id":1010,"code":"LT101.HH","priority":"High","state":"ActiveUnack"'),
               Message := 'LT101.HH snapshot');
AssertEquals_UINT(Expected := 0, Actual := GVL_Iiot.stIiotSts.uiQueue, Message := 'everything published');
AssertEquals_UINT(Expected := UINT#197, Actual := fbFake.uiPubTotal, Message := 'birth, 121 metrics and 75 alarms');

// команда Start: шлюз -> GVL_Hmi -> обработка устройством -> ответ ok
SysTimeRtcHighResGet(pTimestamp := uliNow);
sCmd := CONCAT(CONCAT('{"schema_version":"1.0","cmd_id":"it000001","ts":', ULINT_TO_STRING(uliNow)),
               ',"origin":"test","command":"Start"}');
GVL_Hmi.stP101Cmd.xStart := FALSE;
uiSeq0 := GVL_Devices.fbP101.stSts.stCommon.uiCmdSeq;
fbFake.Inject(sTopic := 'vodokanal/kns1/station/P101/cmd/Start', sPayload := sCmd, xTruncated := FALSE,
    xRetained := FALSE);
PRG_Iiot();
AssertTrue(Condition := GVL_Hmi.stP101Cmd.xStart, Message := 'Start -> GVL_Hmi.stP101Cmd.xStart');
GVL_Devices.fbP101.stSts.stCommon.uiCmdSeq := uiSeq0 + 1;
GVL_Devices.fbP101.stSts.stCommon.eCmdResult := E_CmdResult.Accepted;
PRG_Iiot();
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/cmd_ack/Start',
           sPart := '"cmd_id":"it000001"'), Message := 'ack for it000001');
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/P101/cmd_ack/Start',
           sPart := '"result":"accepted","reason":"ok"}'), Message := 'ok after the device processed the command');
// SpeedSp: значение в GVL_Hmi, ответ сразу
sCmd := CONCAT(CONCAT('{"schema_version":"1.0","cmd_id":"it000002","ts":', ULINT_TO_STRING(uliNow)),
               ',"origin":"test","command":"SpeedSp","value":55.5}');
fbFake.Inject(sTopic := 'vodokanal/kns1/station/P101/cmd/SpeedSp', sPayload := sCmd, xTruncated := FALSE,
              xRetained := FALSE);
PRG_Iiot();
AssertEquals_REAL(Expected := 55.5, Actual := GVL_Hmi.stP101Cmd.rSpeedSp_pct, Delta := 0.0001,
    Message := 'speed setpoint');
// SetOos не в белом списке
sCmd := CONCAT(CONCAT('{"schema_version":"1.0","cmd_id":"it000003","ts":', ULINT_TO_STRING(uliNow)),
               ',"origin":"test","command":"SetOos"}');
fbFake.Inject(sTopic := 'vodokanal/kns1/station/V1/cmd/SetOos', sPayload := sCmd, xTruncated := FALSE,
    xRetained := FALSE);
PRG_Iiot();
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/V1/cmd_ack/SetOos',
           sPart := '"result":"rejected","reason":"not_whitelisted"}'), Message := 'SetOos rejected');
AssertEquals_UDINT(Expected := 2, Actual := GVL_Iiot.stIiotSts.udiCmdAccepted, Message := 'two accepted');

// обмен выключен: штатное отключение, статус C
GVL_Iiot.stIiotCfg.xEnable := FALSE;
PRG_Iiot();
AssertTrue(Condition := fbFake.LastHas(sTopic := 'vodokanal/kns1/station/PLC1/status/connection',
           sPart := '"state":"offline","reason":"shutdown"'), Message := 'shutdown status');
PRG_Iiot.itfClientOverride := 0;
PRG_Iiot();
AssertTrue(Condition := GVL_Iiot.stIiotSts.eNe107 = E_IiotNe107.CheckFunction, Message := 'disabled: C');

coUnit.TEST_FINISHED();
