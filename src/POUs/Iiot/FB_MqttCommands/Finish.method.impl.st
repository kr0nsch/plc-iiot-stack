eLastReason := eReason;
IF eReason = E_IiotCmdReason.Ok THEN
    udiAccepted := udiAccepted + 1;
ELSE
    udiRejected := udiRejected + 1;
END_IF
sPath := CONCAT(CONCAT(sTopicDevice, GVL_Const.TOPIC_SEPARATOR), GVL_Const.TOPIC_ACK_LEVEL);
sPath := CONCAT(CONCAT(sPath, GVL_Const.TOPIC_SEPARATOR), sTopicCommand);
sAckTopic := F_IiotTopic(sPrefix := sTopicPrefix, sPath := sPath);
fbJson.Begin();
fbJson.AddString(sKey := 'schema_version', sValue := GVL_Const.IIOT_SCHEMA_VERSION);
fbJson.AddString(sKey := 'cmd_id', sValue := sCmdId);
fbJson.AddInt(sKey := 'ts', liValue := ULINT_TO_LINT(uliTs_ms));
fbJson.AddString(sKey := 'command', sValue := sTopicCommand);
IF eReason = E_IiotCmdReason.Ok THEN
    fbJson.AddString(sKey := 'result', sValue := 'accepted');
ELSE
    fbJson.AddString(sKey := 'result', sValue := 'rejected');
END_IF
fbJson.AddString(sKey := 'reason', sValue := F_IiotCmdReasonText(eReason := eReason));
sResultText := F_IiotCmdResultText(iResult := iCmdResult);
IF eReason = E_IiotCmdReason.DeviceRejected AND LEN(sResultText) > 0 THEN
    fbJson.AddString(sKey := 'cmd_result', sValue := sResultText);
END_IF
IF NOT fbJson.Finish() OR LEN(sAckTopic) = 0 THEN
    udiAckFailed := udiAckFailed + 1;
ELSIF NOT itfClient.Publish(sTopic := sAckTopic, eQos := E_MqttQos.AtLeastOnce, xRetain := FALSE,
                            sPayload := fbJson.sJson) THEN
    udiAckFailed := udiAckFailed + 1;
END_IF
