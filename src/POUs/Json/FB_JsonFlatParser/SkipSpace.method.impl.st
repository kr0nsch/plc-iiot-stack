WHILE uiPos < uiLen DO
    bCh := sJson[uiPos];
    IF bCh = GVL_Const.ASCII_SPACE OR bCh = GVL_Const.ASCII_TAB OR bCh = GVL_Const.ASCII_LF
       OR bCh = GVL_Const.ASCII_CR THEN
        uiPos := uiPos + 1;
    ELSE
        EXIT;
    END_IF
END_WHILE
