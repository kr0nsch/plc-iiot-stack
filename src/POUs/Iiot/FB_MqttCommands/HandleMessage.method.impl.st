sCmdId := '';
IF NOT SplitTopic() THEN
    udiDropped := udiDropped + 1;      // не команда своей станции — отвечать некуда
    RETURN;
END_IF
IF xRxTruncated OR NOT fbParser.Parse(sJson := sRxPayload) THEN
    udiDropped := udiDropped + 1;      // не JSON-объект: cmd_id не прочитать
    RETURN;
END_IF
IF NOT fbParser.GetString(sKey := 'cmd_id', sValue := sCmdId) OR NOT F_IiotIsCmdId(sText := sCmdId) THEN
    sCmdId := '';
    udiDropped := udiDropped + 1;
    RETURN;
END_IF
eReason := Check(aRuleTable := aRuleTable);
IF eReason <> E_IiotCmdReason.Duplicate THEN
    Remember();
END_IF
IF eReason = E_IiotCmdReason.Ok THEN
    xCmdValid := TRUE;
    xAwaitArm := TRUE;
ELSE
    Finish(eReason := eReason, iCmdResult := 0);
END_IF
