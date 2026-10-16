(*
    Назначение: двигатель с контактором — пуск, стоп, контроль обратной связи
    Автор: <ИМЯ ФАМИЛИЯ>
    Версия: 1.0.0
    Документ: docs/ARCHITECTURE.md
*)
FUNCTION_BLOCK FB_Motor
VAR_INPUT
    stCmd : ST_MotorCmd;            // команды HMI
    xFeedback : BOOL;               // обратная связь контактора
    itfInterlock : I_Resettable;    // связанная блокировка (необязательно)
END_VAR
VAR_OUTPUT
    xRun : BOOL;                    // команда на контактор
    stSts : ST_MotorSts;            // состояние для HMI
END_VAR
VAR
    fbStartTimer : TON;             // контроль обратной связи при пуске
    fbAckEdge : R_TRIG;             // фронт квитирования
    rSpeedSp_rpm : REAL;            // принятая уставка
    pSts : REF_TO ST_MotorSts;
    refCmd : REF_TO ST_MotorCmd;
    iStep : INT := 0;
    wsState : WSTRING[80] := "$041E$0441$0442$0430$043D$043E$0432$043B$0435$043D";
END_VAR
refCmd := ADR(stCmd);
pSts := ADR(stSts);
fbAckEdge(CLK := refCmd.xAck);
IF fbAckEdge.Q THEN
    Reset(xForce := FALSE);
END_IF

CASE eModeInt OF
    0, 1:
        IF refCmd.xStart AND xEnable AND NOT xFault THEN
            xRun := TRUE;
            iStep := GVL_Const.STEP_RUN;
        END_IF
    3:
        xRun := FALSE;
ELSE
    xRun := FALSE;
END_CASE
IF refCmd.xStop OR xFault THEN xRun := FALSE; END_IF;

CASE iStep OF
    0:
        wsState := "$041E$0441$0442$0430$043D$043E$0432$043B$0435$043D";
    10:
        wsState := "$0412$0020$0440$0430$0431$043E$0442$0435";
END_CASE

(* Нет обратной связи за MOTOR_START_TIMEOUT — отказ *)
fbStartTimer(IN := xRun AND NOT xFeedback, PT := GVL_Const.MOTOR_START_TIMEOUT);
IF fbStartTimer.Q THEN xFault := TRUE; END_IF;
IF xFault THEN
    eNamur := E_NamurStatus.Failure;
    wsState := "$0410$0432$0430$0440$0438$044F:$0020$043D$0435$0442$0020$043E$0431$0440$0430$0442$043D$043E$0439$0020$0441$0432$044F$0437$0438";
END_IF

pSts.xRunning := xRun AND xFeedback;
pSts.xFault := xFault;
stSts.eMode := eModeInt;
stSts.eNamur := eNamur;
stSts.rSpeed_rpm := F_Clamp(
    rValue := rSpeedSp_rpm,
    rMin := GVL_Const.MOTOR_SPEED_MIN_RPM,
    rMax := GVL_Const.MOTOR_SPEED_MAX_RPM);
stSts.wsText := wsState;
END_FUNCTION_BLOCK

FUNCTION FB_Motor__Reset : BOOL
VAR_INPUT
    xForce : BOOL;
END_VAR
VAR (* копии переменных FB_Motor — приближение для статанализа *)
    itfInterlock : I_Resettable;
    fbStartTimer : TON;
    iStep : INT := 0;
    Reset : BOOL;
END_VAR
Reset := FB_DeviceBase__Reset(xForce := xForce);
IF itfInterlock <> 0 THEN
    itfInterlock.Reset(xForce := xForce);
END_IF
fbStartTimer(IN := FALSE);
iStep := GVL_Const.STEP_IDLE;
FB_Motor__Reset := Reset;
END_FUNCTION

FUNCTION FB_Motor__Start : BOOL
VAR_INPUT
    rSpeed_rpm : REAL;
END_VAR
VAR (* копии переменных FB_Motor — приближение для статанализа *)
    stSts : ST_MotorSts;
    rSpeedSp_rpm : REAL;
END_VAR
rSpeedSp_rpm := F_Clamp(
    rValue := rSpeed_rpm,
    rMin := GVL_Const.MOTOR_SPEED_MIN_RPM,
    rMax := GVL_Const.MOTOR_SPEED_MAX_RPM);
stSts.xRunning := FALSE;
FB_Motor__Start := TRUE;
END_FUNCTION

FUNCTION FB_Motor__Running__get : BOOL
VAR (* копии переменных FB_Motor — приближение для статанализа *)
    xFeedback : BOOL;
    xRun : BOOL;
    Running : BOOL;
END_VAR
Running := xRun AND xFeedback;
FB_Motor__Running__get := Running;
END_FUNCTION
