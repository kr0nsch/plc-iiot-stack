IF NOT stPoint.xSent OR stPoint.xForce OR stPoint.eQuality <> stPoint.eLastQuality THEN
    PointDue := TRUE;
    RETURN;
END_IF
IF stPoint.stCfg.xPeriodicOnly THEN
    RETURN;
END_IF
IF ltNow >= stPoint.ltLastSent AND_THEN (ltNow - stPoint.ltLastSent) < TIME_TO_LTIME(tMinInterval) THEN
    RETURN;
END_IF
PointDue := F_IiotDeadbandExceeded(lrNew := stPoint.lrValue, lrLast := stPoint.lrLastValue,
                                   rDeadband := stPoint.stCfg.rDeadband);
