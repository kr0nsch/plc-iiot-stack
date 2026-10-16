uiLitLen := INT_TO_UINT(LEN(sLiteral));
IF uiPos + uiLitLen > uiLen THEN
    Fail(eReason := E_JsonError.Syntax);
    RETURN;
END_IF
FOR uiIdx := 0 TO uiLitLen - 1 DO
    IF sJson[uiPos + uiIdx] <> sLiteral[uiIdx] THEN
        uiPos := uiPos + uiIdx;
        Fail(eReason := E_JsonError.Syntax);
        RETURN;
    END_IF
END_FOR
uiPos := uiPos + uiLitLen;
MatchLiteral := TRUE;
