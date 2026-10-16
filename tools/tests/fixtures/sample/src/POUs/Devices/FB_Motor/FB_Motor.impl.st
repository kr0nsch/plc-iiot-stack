refCmd REF= stCmd;
pSts := ADR(stSts);
fbAckEdge(CLK := refCmd.xAck);
IF fbAckEdge.Q THEN
    Reset(xForce := FALSE);
END_IF

CASE eModeInt OF
    E_DeviceMode.Auto, E_DeviceMode.Manual:
        IF refCmd.xStart AND xEnable AND NOT xFault THEN
            xRun := TRUE;
            iStep := GVL_Const.STEP_RUN;
        END_IF
    E_DeviceMode.OutOfService:
        xRun := FALSE;
ELSE
    xRun := FALSE;
END_CASE
xRun R= refCmd.xStop OR xFault;

CASE iStep OF
    GVL_Const.STEP_IDLE:
        wsState := "Остановлен";
    GVL_Const.STEP_RUN:
        wsState := "В работе";
END_CASE

(* Нет обратной связи за MOTOR_START_TIMEOUT — отказ *)
fbStartTimer(IN := xRun AND NOT xFeedback, PT := GVL_Const.MOTOR_START_TIMEOUT);
xFault S= fbStartTimer.Q;
IF xFault THEN
    eNamur := E_NamurStatus.Failure;
    wsState := "Авария: нет обратной связи";
END_IF

pSts^.xRunning := xRun AND xFeedback;
pSts^.xFault := xFault;
stSts.eMode := eModeInt;
stSts.eNamur := eNamur;
stSts.rSpeed_rpm := F_Clamp(
    rValue := rSpeedSp_rpm,
    rMin := GVL_Const.MOTOR_SPEED_MIN_RPM,
    rMax := GVL_Const.MOTOR_SPEED_MAX_RPM);
stSts.wsText := wsState;
