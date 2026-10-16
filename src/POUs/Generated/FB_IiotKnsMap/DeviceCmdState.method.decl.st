// Счётчик обработанных команд и результат последней команды устройства diDev (ST_IiotCmdRule.diDev).
METHOD DeviceCmdState
VAR_INPUT
    diDev : DINT;
END_VAR
VAR_OUTPUT
    uiSeq : UINT;
    iResult : INT;
END_VAR
