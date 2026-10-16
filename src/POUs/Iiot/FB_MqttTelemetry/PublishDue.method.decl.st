// Обход метрик по кругу от diCursor: опубликовать те, что требуют публикации, не больше uiMaxPerCycle.
// Клиент отказал — публикации до следующего вызова прекращаются. uiPending — сколько метрик ждут.
METHOD PRIVATE PublishDue
VAR_IN_OUT
    aPointTable : ARRAY[*] OF ST_IiotPoint;
END_VAR
VAR
    diLo : DINT;
    diTotal : DINT;
    diStep : DINT;
    diIdx : DINT;
    diNextCursor : DINT;
    uiBudget : UINT;
    xBlocked : BOOL;        // клиент не принял сообщение в этом вызове
END_VAR
