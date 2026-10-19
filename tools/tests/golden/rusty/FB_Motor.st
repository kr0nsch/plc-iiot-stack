(*
    Назначение: двигатель с контактором — пуск, стоп, контроль обратной связи
    Автор: kr0nsch
    Версия: 1.0.0
    Документ: docs/ARCHITECTURE.md
*)
FUNCTION_BLOCK FB_Motor EXTENDS FB_DeviceBase
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
    pSts : POINTER TO ST_MotorSts;
    refCmd : REFERENCE TO ST_MotorCmd;
    iStep : INT := STEP_IDLE;
    wsState : WSTRING[80] := "Остановлен";
END_VAR
METHOD PUBLIC Reset : BOOL
VAR_INPUT
    xForce : BOOL;
END_VAR
Reset := SUPER^.Reset(xForce := xForce);
IF __ItfIsSet(ADR(itfInterlock)) THEN
    itfInterlock.Reset(xForce := xForce);
END_IF
fbStartTimer(IN := FALSE);
iStep := STEP_IDLE;
END_METHOD
METHOD PUBLIC Start
VAR_INPUT
    rSpeed_rpm : REAL;
END_VAR
rSpeedSp_rpm := F_Clamp(
    rValue := rSpeed_rpm,
    rMin := MOTOR_SPEED_MIN_RPM,
    rMax := MOTOR_SPEED_MAX_RPM);
THIS^.stSts.xRunning := FALSE;
END_METHOD
// TRUE — двигатель работает (есть команда и обратная связь)
PROPERTY_GET Running : BOOL
Running := xRun AND xFeedback;
END_PROPERTY
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
            iStep := STEP_RUN;
        END_IF
    E_DeviceMode.OutOfService:
        xRun := FALSE;
ELSE
    xRun := FALSE;
END_CASE
IF refCmd.xStop OR xFault THEN xRun := FALSE; END_IF;

CASE iStep OF
    STEP_IDLE:
        wsState := "Остановлен";
    STEP_RUN:
        wsState := "В работе";
END_CASE

(* Нет обратной связи за MOTOR_START_TIMEOUT — отказ *)
fbStartTimer(IN := xRun AND NOT xFeedback, PT := MOTOR_START_TIMEOUT);
IF fbStartTimer.Q THEN xFault := TRUE; END_IF;
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
    rMin := MOTOR_SPEED_MIN_RPM,
    rMax := MOTOR_SPEED_MAX_RPM);
stSts.wsText := wsState;
END_FUNCTION_BLOCK
