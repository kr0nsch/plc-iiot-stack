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
