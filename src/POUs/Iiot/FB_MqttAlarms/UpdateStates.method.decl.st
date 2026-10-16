// Состояние каждой тревоги по словам её устройства; строка слов вне таблицы — тревога в норме.
METHOD PRIVATE UpdateStates
VAR_IN_OUT
    aAlarmTable : ARRAY[*] OF ST_IiotAlarm;
    aWordTable : ARRAY[*] OF ST_IiotAlarmWords;
END_VAR
VAR
    diIdx : DINT;
    diWords : DINT;
END_VAR
