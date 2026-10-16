uiCount := 0;
eError := E_JsonError.None;
uiErrorPos := 0;
uiPos := 0;
uiLen := 0;
WHILE uiLen < GVL_Const.MQTT_CMD_PAYLOAD_LEN AND_THEN sJson[uiLen] <> GVL_Const.ASCII_NUL DO
    uiLen := uiLen + 1;
END_WHILE

SkipSpace(sJson := sJson);
IF uiPos >= uiLen THEN
    Fail(eReason := E_JsonError.Empty);
    RETURN;
END_IF
IF Peek(sJson := sJson) <> GVL_Const.ASCII_LBRACE THEN
    Fail(eReason := E_JsonError.Syntax);
    RETURN;
END_IF
uiPos := uiPos + 1;
SkipSpace(sJson := sJson);

IF Peek(sJson := sJson) = GVL_Const.ASCII_RBRACE THEN
    uiPos := uiPos + 1;      // пустой объект {}
ELSE
    WHILE TRUE DO
        // ключ
        IF Peek(sJson := sJson) <> GVL_Const.ASCII_QUOTE THEN
            Fail(eReason := E_JsonError.Syntax);
            RETURN;
        END_IF
        IF NOT ParseText(sJson := sJson, uiMaxLen := GVL_Const.JSON_KEY_LEN, eTooLong := E_JsonError.KeyTooLong) THEN
            RETURN;
        END_IF
        stField.sKey := sTok;
        stField.sText := '';
        stField.lrNumber := 0.0;
        stField.xInteger := FALSE;
        stField.xBool := FALSE;
        SkipSpace(sJson := sJson);
        IF Peek(sJson := sJson) <> GVL_Const.ASCII_COLON THEN
            Fail(eReason := E_JsonError.Syntax);
            RETURN;
        END_IF
        uiPos := uiPos + 1;
        SkipSpace(sJson := sJson);

        // значение
        bCh := Peek(sJson := sJson);
        IF bCh = GVL_Const.ASCII_QUOTE THEN
            IF NOT ParseText(sJson := sJson, uiMaxLen := GVL_Const.JSON_STR_LEN,
                             eTooLong := E_JsonError.ValueTooLong) THEN
                RETURN;
            END_IF
            stField.eType := E_JsonType.Text;
            stField.sText := sTok;
        ELSIF bCh = GVL_Const.ASCII_MINUS OR (bCh >= GVL_Const.ASCII_ZERO AND bCh <= GVL_Const.ASCII_NINE) THEN
            IF NOT ParseNumber(sJson := sJson) THEN
                RETURN;
            END_IF
            stField.eType := E_JsonType.Number;
            stField.lrNumber := lrTok;
            stField.xInteger := xTokInteger;
        ELSIF bCh = GVL_Const.ASCII_LOWER_T THEN
            IF NOT MatchLiteral(sJson := sJson, sLiteral := 'true') THEN
                RETURN;
            END_IF
            stField.eType := E_JsonType.Boolean;
            stField.xBool := TRUE;
        ELSIF bCh = GVL_Const.ASCII_LOWER_F THEN
            IF NOT MatchLiteral(sJson := sJson, sLiteral := 'false') THEN
                RETURN;
            END_IF
            stField.eType := E_JsonType.Boolean;
        ELSIF bCh = GVL_Const.ASCII_LOWER_N THEN
            IF NOT MatchLiteral(sJson := sJson, sLiteral := 'null') THEN
                RETURN;
            END_IF
            stField.eType := E_JsonType.NullValue;
        ELSIF bCh = GVL_Const.ASCII_LBRACE OR bCh = GVL_Const.ASCII_LBRACKET THEN
            Fail(eReason := E_JsonError.Nested);
            RETURN;
        ELSE
            Fail(eReason := E_JsonError.Syntax);
            RETURN;
        END_IF

        IF FindField(sKey := stField.sKey) > 0 THEN
            Fail(eReason := E_JsonError.Duplicate);
            RETURN;
        END_IF
        IF uiCount >= GVL_Const.JSON_MAX_FIELDS THEN
            Fail(eReason := E_JsonError.TooManyFields);
            RETURN;
        END_IF
        uiCount := uiCount + 1;
        aFields[uiCount] := stField;

        SkipSpace(sJson := sJson);
        bCh := Peek(sJson := sJson);
        IF bCh = GVL_Const.ASCII_COMMA THEN
            uiPos := uiPos + 1;
            SkipSpace(sJson := sJson);
        ELSIF bCh = GVL_Const.ASCII_RBRACE THEN
            uiPos := uiPos + 1;
            EXIT;
        ELSE
            Fail(eReason := E_JsonError.Syntax);
            RETURN;
        END_IF
    END_WHILE
END_IF

SkipSpace(sJson := sJson);
IF uiPos < uiLen THEN
    Fail(eReason := E_JsonError.Trailing);
    RETURN;
END_IF
Parse := TRUE;
