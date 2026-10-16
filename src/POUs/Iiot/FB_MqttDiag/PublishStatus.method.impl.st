sTopic := StatusTopic();
IF NOT BuildStatus(xOnline := xOnline, sReason := sReason) OR LEN(sTopic) = 0 THEN
    RETURN;
END_IF
PublishStatus := itfClient.Publish(sTopic := sTopic, eQos := E_MqttQos.AtLeastOnce, xRetain := TRUE,
                                   sPayload := fbJson.sJson);
