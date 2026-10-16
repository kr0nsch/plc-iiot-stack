FOR uiIdx := 1 TO GVL_Const.CMD_HISTORY_LEN DO
    IF LEN(aHistory[uiIdx]) > 0 AND aHistory[uiIdx] = sCmdId THEN
        IsDuplicate := TRUE;
        RETURN;
    END_IF
END_FOR
