sTopicDevice := '';
sTopicCommand := '';
iPrefixLen := LEN(sTopicPrefix);
IF iPrefixLen = 0 OR LEN(sRxTopic) <= iPrefixLen + 1 THEN
    RETURN;
END_IF
IF LEFT(sRxTopic, iPrefixLen) <> sTopicPrefix OR MID(sRxTopic, 1, iPrefixLen + 1) <> GVL_Const.TOPIC_SEPARATOR THEN
    RETURN;
END_IF
sRest := RIGHT(sRxTopic, LEN(sRxTopic) - iPrefixLen - 1);
// <DEVICE>
iSlash := FIND(sRest, GVL_Const.TOPIC_SEPARATOR);
IF iSlash <= 1 OR iSlash - 1 > UINT_TO_INT(GVL_Const.IIOT_DEVICE_LEN) THEN
    RETURN;
END_IF
sTopicDevice := LEFT(sRest, iSlash - 1);
sTail := RIGHT(sRest, LEN(sRest) - iSlash);
// cmd
iSlash := FIND(sTail, GVL_Const.TOPIC_SEPARATOR);
IF iSlash <= 1 OR LEFT(sTail, iSlash - 1) <> GVL_Const.TOPIC_CMD_LEVEL THEN
    sTopicDevice := '';
    RETURN;
END_IF
// <Command>
IF LEN(sTail) - iSlash > UINT_TO_INT(GVL_Const.IIOT_LEVEL_LEN) THEN
    sTopicDevice := '';
    RETURN;
END_IF
sTopicCommand := RIGHT(sTail, LEN(sTail) - iSlash);
IF NOT F_IiotIsName(sText := sTopicDevice, iMaxLen := UINT_TO_INT(GVL_Const.IIOT_DEVICE_LEN), xUpperOnly := TRUE)
   OR NOT F_IiotIsName(sText := sTopicCommand, iMaxLen := UINT_TO_INT(GVL_Const.IIOT_LEVEL_LEN),
                       xUpperOnly := FALSE) THEN
    sTopicDevice := '';
    sTopicCommand := '';
    RETURN;
END_IF
SplitTopic := TRUE;
