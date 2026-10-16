sTok := '';
uiOut := 0;
uiPos := uiPos + 1;   // за открывающую кавычку
WHILE TRUE DO
    IF uiPos >= uiLen THEN
        Fail(eReason := E_JsonError.Syntax);   // строка не закрыта
        RETURN;
    END_IF
    bCh := sJson[uiPos];
    IF bCh = GVL_Const.ASCII_QUOTE THEN
        uiPos := uiPos + 1;
        EXIT;
    END_IF
    IF bCh <= GVL_Const.ASCII_CTRL_LAST THEN
        Fail(eReason := E_JsonError.Syntax);
        RETURN;
    END_IF
    IF bCh = GVL_Const.ASCII_BACKSLASH THEN
        uiPos := uiPos + 1;
        IF uiPos >= uiLen THEN
            Fail(eReason := E_JsonError.Syntax);
            RETURN;
        END_IF
        bCh := sJson[uiPos];
        // после обратной косой черты: кавычка, обратная и прямая косая черта дают сами себя
        IF bCh = GVL_Const.ASCII_LOWER_N THEN
            bCh := GVL_Const.ASCII_LF;
        ELSIF bCh = GVL_Const.ASCII_LOWER_R THEN
            bCh := GVL_Const.ASCII_CR;
        ELSIF bCh = GVL_Const.ASCII_LOWER_T THEN
            bCh := GVL_Const.ASCII_TAB;
        ELSIF bCh = GVL_Const.ASCII_LOWER_B THEN
            bCh := GVL_Const.ASCII_BS;
        ELSIF bCh = GVL_Const.ASCII_LOWER_F THEN
            bCh := GVL_Const.ASCII_FF;
        ELSIF bCh = GVL_Const.ASCII_LOWER_U THEN
            uiCode := 0;
            FOR uiHex := 1 TO GVL_Const.HEX_DIGITS_ESCAPE DO
                IF uiPos + uiHex >= uiLen THEN
                    Fail(eReason := E_JsonError.BadEscape);
                    RETURN;
                END_IF
                iDigit := HexValue(bDigit := sJson[uiPos + uiHex]);
                IF iDigit < 0 THEN
                    Fail(eReason := E_JsonError.BadEscape);
                    RETURN;
                END_IF
                uiCode := uiCode * GVL_Const.HEX_BASE + INT_TO_UINT(iDigit);
            END_FOR
            // поддерживаются только символы ASCII без нуля
            IF uiCode = 0 OR uiCode > BYTE_TO_UINT(GVL_Const.ASCII_LAST) THEN
                Fail(eReason := E_JsonError.BadEscape);
                RETURN;
            END_IF
            uiPos := uiPos + GVL_Const.HEX_DIGITS_ESCAPE;
            bCh := UINT_TO_BYTE(uiCode);
        ELSIF bCh <> GVL_Const.ASCII_QUOTE AND bCh <> GVL_Const.ASCII_BACKSLASH AND bCh <> GVL_Const.ASCII_SLASH THEN
            Fail(eReason := E_JsonError.BadEscape);
            RETURN;
        END_IF
    END_IF
    IF uiOut >= uiMaxLen THEN
        Fail(eReason := eTooLong);
        RETURN;
    END_IF
    sTok[uiOut] := bCh;
    uiOut := uiOut + 1;
    sTok[uiOut] := GVL_Const.ASCII_NUL;
    uiPos := uiPos + 1;
END_WHILE
ParseText := TRUE;
