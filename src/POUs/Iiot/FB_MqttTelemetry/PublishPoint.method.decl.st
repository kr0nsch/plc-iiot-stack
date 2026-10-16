// Опубликовать метрику: {"schema_version","ts","value","quality"[,"unit"]}. TRUE — метрика обработана
// (опубликована или пропущена из-за переполнения); FALSE — клиент не принял, она повторится.
// Значение не конечно (NaN, ±Inf): схема требует число, поэтому передаётся последнее опубликованное
// конечное значение с quality = bad (data_schema 3.2).
METHOD PRIVATE PublishPoint : BOOL
VAR_IN_OUT
    stPoint : ST_IiotPoint;
END_VAR
VAR
    xFinite : BOOL;
    lrOut : LREAL;
    eOutQuality : E_IiotQuality;
END_VAR
