IF uiHistoryNext < 1 OR uiHistoryNext > GVL_Const.CMD_HISTORY_LEN THEN
    uiHistoryNext := 1;
END_IF
aHistory[uiHistoryNext] := sCmdId;
uiHistoryNext := uiHistoryNext + 1;
