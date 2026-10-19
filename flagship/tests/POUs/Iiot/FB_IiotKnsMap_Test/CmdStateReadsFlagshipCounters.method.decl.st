// Счётчик и результат команды: станция — stStationSts, регулятор — fbLIC101.stSts; чужой номер — нули.
METHOD PRIVATE CmdStateReadsFlagshipCounters
VAR
    stStsSaved : ST_StationSts;
    diDev : DINT;
    uiSeq : UINT;
    iResult : INT;
END_VAR
