// Принятая команда — в структуру команд флагмана: импульс или значение; строка вне таблицы — FALSE.
METHOD PRIVATE CommandsGoToFlagshipCmdStructs
VAR
    stP102Saved : PL.ST_MotorCmd;
    stP103Saved : PL.ST_MotorCmd;
    stStationSaved : ST_StationCmd;
    stLic101Saved : PL.ST_PidCmd;
    diRule : DINT;
END_VAR
