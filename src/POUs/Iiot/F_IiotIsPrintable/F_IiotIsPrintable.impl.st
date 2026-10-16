iLen := LEN(sText);
IF iLen < 1 OR iLen > iMaxLen THEN
    RETURN;
END_IF
FOR iIdx := 0 TO iLen - 1 DO
    bCh := sText[iIdx];
    IF bCh < GVL_Const.ASCII_SPACE OR bCh > GVL_Const.ASCII_TILDE THEN
        RETURN;
    END_IF
END_FOR
F_IiotIsPrintable := TRUE;
