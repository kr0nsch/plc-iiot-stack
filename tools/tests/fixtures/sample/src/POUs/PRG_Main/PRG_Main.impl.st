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
