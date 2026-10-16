IF NOT xAwaitArm THEN
    RETURN;
END_IF
xAwaitArm := FALSE;
IF F_IiotCmdKind(eCommand := stCmd.eCommand) = E_IiotCmdKind.Value THEN
    Finish(eReason := E_IiotCmdReason.Ok, iCmdResult := 0);
ELSE
    uiSeqArmed := uiSeqBefore;
    ltPendingSince := ltNow;
    xPending := TRUE;
END_IF
