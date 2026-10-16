uiLimit := MIN(MAX(uiRateLimit, 1), GVL_Const.CMD_RATE_LIMIT);
IF uiRateNext < 1 OR uiRateNext > uiLimit THEN
    uiRateNext := 1;
END_IF
// в кольце из uiLimit моментов следующая позиция — самая старая из последних uiLimit команд
IF uiRateCount >= uiLimit AND_THEN ltNow >= aRateTimes[uiRateNext]
   AND_THEN (ltNow - aRateTimes[uiRateNext]) <= TIME_TO_LTIME(tRateWindow) THEN
    RETURN;
END_IF
aRateTimes[uiRateNext] := ltNow;
uiRateNext := uiRateNext + 1;
IF uiRateNext > uiLimit THEN
    uiRateNext := 1;
END_IF
IF uiRateCount < uiLimit THEN
    uiRateCount := uiRateCount + 1;
END_IF
RateAllows := TRUE;
