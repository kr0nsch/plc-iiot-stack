// Обход тревог по кругу: не опубликована с подключения (снимок или повтор) или состояние изменилось (событие).
METHOD PRIVATE PublishDue
VAR_IN_OUT
    aAlarmTable : ARRAY[*] OF ST_IiotAlarm;
END_VAR
VAR
    diLo : DINT;
    diTotal : DINT;
    diStep : DINT;
    diIdx : DINT;
    diNextCursor : DINT;
    uiBudget : UINT;
    xBlocked : BOOL;
END_VAR
