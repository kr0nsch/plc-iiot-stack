// Вызвать после записи stCmd в GVL_Hmi в том же цикле: uiSeqBefore — uiCmdSeq устройства до записи.
// Команды-значения (SpeedSp, SubstValue) отвечают ok сразу: ФБ устройства их не квитирует.
METHOD Arm
VAR_INPUT
    uiSeqBefore : UINT;
END_VAR
