(* Вспомогательная функция совместимости для проверки RuSTy (не для CODESYS):
   проверка, что интерфейсная переменная задана (itfX <> 0 в CODESYS). *)
FUNCTION __ItfIsSet : BOOL
VAR_INPUT
    pFat : POINTER TO LWORD;
END_VAR
__ItfIsSet := pFat^ <> 0;
END_FUNCTION

{attribute 'qualified_only'}
{attribute 'strict'}
// Режим работы устройства (docs/ARCHITECTURE.md, раздел «Режимы»)
TYPE E_DeviceMode :
(
    Auto := 0,          // автоматический
    Manual := 1,        // ручной с HMI
    Local := 2,         // местный пост
    OutOfService := 3   // выведен из работы
) INT;
END_TYPE

{attribute 'qualified_only'}
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
    eMode : E_DeviceMode := E_DeviceMode.Auto;      // заданный режим
    rSpeedSp_rpm : REAL;                            // уставка скорости
END_STRUCT
END_TYPE

// Состояние двигателя: общее состояние устройства плюс данные привода
TYPE ST_MotorSts :
STRUCT eMode : E_DeviceMode; eNamur : E_NamurStatus; xFault : BOOL;
    xRunning : BOOL;
    rSpeed_rpm : REAL;
    aLastFaults : ARRAY[1..3] OF E_NamurStatus;    // последние отказы
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

{attribute 'qualified_only'}
// Константы проекта: в логике нет «магических чисел»
VAR_GLOBAL CONSTANT
    MOTOR_START_TIMEOUT : TIME := T#5S;     // ожидание обратной связи при пуске
    MOTOR_SPEED_MAX_RPM : REAL := 1500.0;   // верхняя граница уставки
    MOTOR_SPEED_MIN_RPM : REAL := 0.0;      // нижняя граница уставки
    STEP_IDLE : INT := 0;
    STEP_RUN : INT := 10;
END_VAR

// Сигналы ввода-вывода (привязка к каналам — в дереве устройств, docs/MANUAL_STEPS.md)
VAR_GLOBAL
    xMotorFeedback : BOOL;      // обратная связь контактора
    xMotorRun : BOOL;           // команда на контактор
    stMotorCmd : ST_MotorCmd;   // команды HMI
    stMotorSts : ST_MotorSts;   // состояние для HMI
    uRaw : U_RawValue;          // сырое значение Modbus
END_VAR

VAR_GLOBAL RETAIN
    udiMotorStarts : UDINT;     // счётчик пусков двигателя
END_VAR

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
PROPERTY_GET Mode : E_DeviceMode
END_PROPERTY
PROPERTY_SET Mode : E_DeviceMode
END_PROPERTY
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
FUNCTION_BLOCK ABSTRACT FB_DeviceBase IMPLEMENTS I_Device
VAR_INPUT
    xEnable : BOOL := TRUE;     // разрешение работы
END_VAR
VAR_OUTPUT
    xFault : BOOL;              // отказ
    eNamur : E_NamurStatus := E_NamurStatus.Good;
END_VAR
VAR
    eModeInt : E_DeviceMode := E_DeviceMode.Auto;
END_VAR
METHOD PUBLIC Reset : BOOL
VAR_INPUT
    xForce : BOOL;
END_VAR
xFault := FALSE;
eNamur := E_NamurStatus.Good;
Reset := TRUE;
END_METHOD
METHOD PUBLIC ABSTRACT Start
VAR_INPUT
    rSpeed_rpm : REAL;
END_VAR
END_METHOD
PROPERTY_GET Mode : E_DeviceMode
Mode := eModeInt;
END_PROPERTY
PROPERTY_SET Mode : E_DeviceMode
eModeInt := Mode;
END_PROPERTY
// Общего тела нет: логика — в производных блоках
END_FUNCTION_BLOCK

(*
    Назначение: тесты CfUnit для F_Clamp — граничные условия и перепутанные границы
    Автор: <ИМЯ ФАМИЛИЯ>
    Версия: 1.0.0
    Документ: docs/TEST_REPORT.md
*)
FUNCTION_BLOCK FB_F_Clamp_Test EXTENDS FB_TestSuite
VAR
END_VAR
METHOD PRIVATE SwappedLimits
VAR
    rResult : REAL;
END_VAR
TEST('SwappedLimits');
rResult := F_Clamp(rValue := 5.0, rMin := 10.0, rMax := 0.0);
AssertEquals_REAL(Expected := 10.0, Actual := rResult, Delta := 0.001, Message := 'swapped limits give min');
TEST_FINISHED();
END_METHOD
METHOD PRIVATE ValueBelowMin
VAR
    rResult : REAL;
END_VAR
TEST('ValueBelowMin');
rResult := F_Clamp(rValue := -5.0, rMin := 0.0, rMax := 10.0);
AssertEquals_REAL(Expected := 0.0, Actual := rResult, Delta := 0.001, Message := 'below min gives min');
TEST_FINISHED();
END_METHOD
METHOD PRIVATE ValueInsideRange
VAR
    rResult : REAL;
END_VAR
TEST('ValueInsideRange');
rResult := F_Clamp(rValue := 5.0, rMin := 0.0, rMax := 10.0);
AssertEquals_REAL(Expected := 5.0, Actual := rResult, Delta := 0.001, Message := 'value inside range');
TEST_FINISHED();
END_METHOD
ValueInsideRange();
ValueBelowMin();
SwappedLimits();
END_FUNCTION_BLOCK

(*
    Назначение: двигатель с контактором — пуск, стоп, контроль обратной связи
    Автор: <ИМЯ ФАМИЛИЯ>
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
    stCmd := stMotorCmd,
    xFeedback := xMotorFeedback,
    xRun => xMotorRun);

IF __ItfIsSet(ADR(itfDevice)) AND stMotorCmd.eMode <> itfDevice.Mode THEN
    itfDevice.Mode := stMotorCmd.eMode;
END_IF

// Счётчик пусков — по фронту события, а не счёт циклов
fbRunEdge(CLK := fbMotor.Running);
IF fbRunEdge.Q THEN
    udiMotorStarts := udiMotorStarts + 1;
END_IF
stMotorSts := fbMotor.stSts;
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
RUN();
END_PROGRAM
