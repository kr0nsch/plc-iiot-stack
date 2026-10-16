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
