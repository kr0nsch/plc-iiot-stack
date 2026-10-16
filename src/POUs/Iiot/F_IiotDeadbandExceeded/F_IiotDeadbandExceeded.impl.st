xNewFinite := F_IsFiniteLreal(lrValue := lrNew);
xLastFinite := F_IsFiniteLreal(lrValue := lrLast);
IF NOT xNewFinite OR NOT xLastFinite THEN
    F_IiotDeadbandExceeded := xNewFinite <> xLastFinite;
    RETURN;
END_IF
lrDiff := ABS(lrNew - lrLast);
IF NOT F_IsFiniteReal(rValue := rDeadband) OR rDeadband <= 0.0 THEN
    F_IiotDeadbandExceeded := lrDiff > 0.0;
ELSE
    F_IiotDeadbandExceeded := lrDiff > REAL_TO_LREAL(rDeadband);
END_IF
