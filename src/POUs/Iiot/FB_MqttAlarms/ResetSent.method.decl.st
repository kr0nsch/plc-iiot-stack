// Связи нет: после рождения узла публикуются все тревоги (повтор, событие или снимок — PublishAlarm).
METHOD PRIVATE ResetSent
VAR_IN_OUT
    aAlarmTable : ARRAY[*] OF ST_IiotAlarm;
END_VAR
VAR
    diIdx : DINT;
END_VAR
