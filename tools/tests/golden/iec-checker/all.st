

// Режим работы устройства (docs/ARCHITECTURE.md, раздел «Режимы»)
TYPE E_DeviceMode :
(
    Auto := 0,          // автоматический
    Manual := 1,        // ручной с HMI
    Local := 2,         // местный пост
    OutOfService := 3   // выведен из работы
) ;
END_TYPE


// Статус диагностики по NAMUR NE 107 (названия — сверить с источником)
TYPE E_NamurStatus :
(
    Good,
    CheckFunction,
    OutOfSpecification,
    MaintenanceRequired,
    Failure
);
END_TYPE

// Общее состояние устройства для HMI/SCADA
TYPE ST_DeviceSts :
STRUCT
    eMode : E_DeviceMode;
    eNamur : E_NamurStatus;
    xFault : BOOL;
END_STRUCT
END_TYPE

// Команды двигателя от HMI/SCADA
TYPE ST_MotorCmd :
STRUCT
    xStart : BOOL;                                  // пуск
    xStop : BOOL;                                   // стоп
    xAck : BOOL;                                    // квитирование
    eMode : E_DeviceMode;      // заданный режим
    rSpeedSp_rpm : REAL;                            // уставка скорости
END_STRUCT
END_TYPE

// Состояние двигателя: общее состояние устройства плюс данные привода
TYPE ST_MotorSts :
STRUCT eMode : E_DeviceMode; eNamur : E_NamurStatus; xFault : BOOL;
    xRunning : BOOL;
    rSpeed_rpm : REAL;
    aLastFaults : E_NamurStatus;    // последние отказы
    wsText : WSTRING[80];                           // текст состояния для HMI
END_STRUCT
END_TYPE

// Сырое значение из регистра Modbus: как DWORD или как REAL
TYPE U_RawValue :
STRUCT
    dwRaw : DWORD;
    rValue : REAL;
END_STRUCT
END_TYPE

CONFIGURATION GVL_Const

// Константы проекта: в логике нет «магических чисел»
VAR_GLOBAL CONSTANT
    MOTOR_START_TIMEOUT : TIME := T#5S;     // ожидание обратной связи при пуске
    MOTOR_SPEED_MAX_RPM : REAL := 1500.0;   // верхняя граница уставки
    MOTOR_SPEED_MIN_RPM : REAL := 0.0;      // нижняя граница уставки
    STEP_IDLE : INT := 0;
    STEP_RUN : INT := 10;
END_VAR
END_CONFIGURATION

CONFIGURATION GVL_Io
// Сигналы ввода-вывода (привязка к каналам — в дереве устройств, docs/MANUAL_STEPS.md)
VAR_GLOBAL
    xMotorFeedback : BOOL;      // обратная связь контактора
    xMotorRun : BOOL;           // команда на контактор
    stMotorCmd : ST_MotorCmd;   // команды HMI
    stMotorSts : ST_MotorSts;   // состояние для HMI
    uRaw : U_RawValue;          // сырое значение Modbus
END_VAR
END_CONFIGURATION

CONFIGURATION PVL_Retain
VAR_GLOBAL RETAIN
    udiMotorStarts : UDINT;     // счётчик пусков двигателя
END_VAR
END_CONFIGURATION

// Сброс отказа (квитирование)
INTERFACE I_Resettable
// Сброс; TRUE — отказ сброшен
METHOD Reset : BOOL
VAR_INPUT
    xForce : BOOL;  // сброс без проверки условий
END_VAR
END_METHOD
END_INTERFACE

// Устройство с режимами работы
INTERFACE I_Device EXTENDS I_Resettable
METHOD Start
VAR_INPUT
    rSpeed_rpm : REAL;  // уставка скорости
END_VAR
END_METHOD
METHOD Mode__get : E_DeviceMode
END_METHOD
METHOD Mode__set
VAR_INPUT
    Mode : E_DeviceMode;
END_VAR
END_METHOD
END_INTERFACE

(*
    Назначение: ограничение значения диапазоном [rMin, rMax]
    Автор: <ИМЯ ФАМИЛИЯ>
    Версия: 1.0.0
    Документ: docs/ARCHITECTURE.md
*)
FUNCTION F_Clamp : REAL
VAR_INPUT
    rValue : REAL;  // входное значение
    rMin : REAL;    // нижняя граница
    rMax : REAL;    // верхняя граница
END_VAR
// При перепутанных границах возвращаем нижнюю — безопасное значение
IF rMin > rMax THEN
    F_Clamp := rMin;
ELSE
    F_Clamp := LIMIT(rMin, rValue, rMax);
END_IF
END_FUNCTION

(*
    Назначение: базовый блок устройства — режим, диагностика NE 107, квитирование
    Автор: <ИМЯ ФАМИЛИЯ>
    Версия: 1.0.0
    Документ: docs/ARCHITECTURE.md
*)
FUNCTION_BLOCK FB_DeviceBase
VAR_INPUT
    xEnable : BOOL := TRUE;     // разрешение работы
END_VAR
VAR_OUTPUT
    xFault : BOOL;              // отказ
    eNamur : E_NamurStatus;
END_VAR
VAR
    eModeInt : E_DeviceMode;
END_VAR
// Общего тела нет: логика — в производных блоках
END_FUNCTION_BLOCK

FUNCTION FB_DeviceBase__Reset : BOOL
VAR_INPUT
    xForce : BOOL;
END_VAR
VAR (* копии переменных FB_DeviceBase — приближение для статанализа *)
    xFault : BOOL;
    eNamur : E_NamurStatus;
    Reset : BOOL;
END_VAR
xFault := FALSE;
eNamur := E_NamurStatus.Good;
Reset := TRUE;
FB_DeviceBase__Reset := Reset;
END_FUNCTION

FUNCTION FB_DeviceBase__Start : BOOL
VAR_INPUT
    rSpeed_rpm : REAL;
END_VAR
FB_DeviceBase__Start := TRUE;
END_FUNCTION

FUNCTION FB_DeviceBase__Mode__get : E_DeviceMode
VAR (* копии переменных FB_DeviceBase — приближение для статанализа *)
    eModeInt : E_DeviceMode;
    Mode : E_DeviceMode;
END_VAR
Mode := eModeInt;
FB_DeviceBase__Mode__get := Mode;
END_FUNCTION

FUNCTION FB_DeviceBase__Mode__set : BOOL
VAR_INPUT
    Mode : E_DeviceMode;
END_VAR
VAR (* копии переменных FB_DeviceBase — приближение для статанализа *)
    eModeInt : E_DeviceMode;
END_VAR
eModeInt := Mode;
FB_DeviceBase__Mode__set := TRUE;
END_FUNCTION

(*
    Назначение: тесты CfUnit для F_Clamp — граничные условия и перепутанные границы
    Автор: <ИМЯ ФАМИЛИЯ>
    Версия: 1.0.0
    Документ: docs/TEST_REPORT.md
*)
FUNCTION_BLOCK FB_F_Clamp_Test
VAR
END_VAR
ValueInsideRange();
ValueBelowMin();
SwappedLimits();
END_FUNCTION_BLOCK

FUNCTION FB_F_Clamp_Test__SwappedLimits : BOOL
VAR
    rResult : REAL;
END_VAR
TEST('SwappedLimits');
rResult := F_Clamp(rValue := 5.0, rMin := 10.0, rMax := 0.0);
AssertEquals_REAL(Expected := 10.0, Actual := rResult, Delta := 0.001, Message := 'swapped$20limits$20give$20min');
TEST_FINISHED();
FB_F_Clamp_Test__SwappedLimits := TRUE;
END_FUNCTION

FUNCTION FB_F_Clamp_Test__ValueBelowMin : BOOL
VAR
    rResult : REAL;
END_VAR
TEST('ValueBelowMin');
rResult := F_Clamp(rValue := -5.0, rMin := 0.0, rMax := 10.0);
AssertEquals_REAL(Expected := 0.0, Actual := rResult, Delta := 0.001, Message := 'below$20min$20gives$20min');
TEST_FINISHED();
FB_F_Clamp_Test__ValueBelowMin := TRUE;
END_FUNCTION

FUNCTION FB_F_Clamp_Test__ValueInsideRange : BOOL
VAR
    rResult : REAL;
END_VAR
TEST('ValueInsideRange');
rResult := F_Clamp(rValue := 5.0, rMin := 0.0, rMax := 10.0);
AssertEquals_REAL(Expected := 5.0, Actual := rResult, Delta := 0.001, Message := 'value$20inside$20range');
TEST_FINISHED();
FB_F_Clamp_Test__ValueInsideRange := TRUE;
END_FUNCTION

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

(*
    Назначение: главная программа — двигатель, выдача выходов, счётчик пусков
    Автор: <ИМЯ ФАМИЛИЯ>
    Версия: 1.0.0
    Документ: docs/ARCHITECTURE.md
*)
PROGRAM PRG_Main
VAR
    fbMotor : FB_Motor;
    fbRunEdge : R_TRIG;
    itfDevice : I_Device;
    xInit : BOOL;
END_VAR
IF NOT xInit THEN
    itfDevice := fbMotor;
    xInit := TRUE;
END_IF

fbMotor(
    stCmd := GVL_Io.stMotorCmd,
    xFeedback := GVL_Io.xMotorFeedback,
    xRun => GVL_Io.xMotorRun);

IF itfDevice <> 0 AND GVL_Io.stMotorCmd.eMode <> itfDevice.Mode THEN
    itfDevice.Mode := GVL_Io.stMotorCmd.eMode;
END_IF

// Счётчик пусков — по фронту события, а не счёт циклов
fbRunEdge(CLK := fbMotor.Running);
IF fbRunEdge.Q THEN
    udiMotorStarts := udiMotorStarts + 1;
END_IF
GVL_Io.stMotorSts := fbMotor.stSts;
END_PROGRAM

(*
    Назначение: запуск тестов CfUnit
    Автор: <ИМЯ ФАМИЛИЯ>
    Версия: 1.0.0
    Документ: docs/TEST_REPORT.md
*)
PROGRAM PRG_Tests
VAR
    fbClampTest : FB_F_Clamp_Test;
END_VAR
CfUnit.RUN();
END_PROGRAM
