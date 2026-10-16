IF ltNow >= ltStart THEN
    aPoints[GVL_IiotMap.PT_PLC1_UPTIME].lrValue := ULINT_TO_LREAL(LTIME_TO_ULINT(ltNow - ltStart) / NS_PER_S);
END_IF
IF fbDiag.udiConnects > 0 THEN
    aPoints[GVL_IiotMap.PT_PLC1_RECONNECTS].lrValue := UDINT_TO_LREAL(fbDiag.udiConnects - 1);
END_IF
aPoints[GVL_IiotMap.PT_PLC1_QUEUE].lrValue := UINT_TO_LREAL(fbTelemetry.uiPending + fbAlarms.uiPending);
aPoints[GVL_IiotMap.PT_PLC1_DROPPED].lrValue :=
    UDINT_TO_LREAL(fbTelemetry.udiDropped + fbAlarms.udiDropped + fbCommands.udiAckFailed);
aPoints[GVL_IiotMap.PT_PLC1_CMD_ACCEPTED].lrValue := UDINT_TO_LREAL(fbCommands.udiAccepted);
aPoints[GVL_IiotMap.PT_PLC1_CMD_REJECTED].lrValue := UDINT_TO_LREAL(fbCommands.udiRejected + fbCommands.udiDropped);
aPoints[GVL_IiotMap.PT_PLC1_UPTIME].eQuality := E_IiotQuality.Good;
aPoints[GVL_IiotMap.PT_PLC1_RECONNECTS].eQuality := E_IiotQuality.Good;
aPoints[GVL_IiotMap.PT_PLC1_QUEUE].eQuality := E_IiotQuality.Good;
aPoints[GVL_IiotMap.PT_PLC1_DROPPED].eQuality := E_IiotQuality.Good;
aPoints[GVL_IiotMap.PT_PLC1_CMD_ACCEPTED].eQuality := E_IiotQuality.Good;
aPoints[GVL_IiotMap.PT_PLC1_CMD_REJECTED].eQuality := E_IiotQuality.Good;
