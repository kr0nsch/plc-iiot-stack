IF NOT xBound THEN
    FOR uiSlot := 1 TO PUB_POOL DO
        aPublishers[uiSlot].SetMqttInOut(MQTT_IN_OUT := ADR(stInOut));
    END_FOR
    fbSubscriber.SetMqttInOut(MQTT_IN_OUT := ADR(stInOut));
    xBound := TRUE;
END_IF

fbHandler(ENABLE := xEnable, URL := sUrl, TIMEOUT := tTimeout, TLS := xTls, MQTT_INFO := stInfo,
    MQTT_IN_OUT := stInOut);
IF fbHandler.ERROR_C <> 0 THEN
    diError := DWORD_TO_DINT(fbHandler.ERROR_C);
END_IF

FOR uiSlot := 1 TO PUB_POOL DO
    aPublishers[uiSlot](Topic := ADR(aPubTopic[uiSlot]), PayloadString := 0, PublishAsString := FALSE,
                        Payload := ADR(aPubPayload[uiSlot]), PayloadLength := aPubLen[uiSlot], QoSIn := aPubQos[uiSlot],
                        MRetain := aPubRetain[uiSlot], send := aPubState[uiSlot] = SLOT_SENDING);
    IF aPubState[uiSlot] = SLOT_SENDING THEN
        IF aPublishers[uiSlot].SendTimeout THEN
            diError := MQTT_ERR_SEND_TIMEOUT;
            aPubState[uiSlot] := SLOT_RELEASE;
        ELSIF aPublishers[uiSlot].done THEN
            aPubState[uiSlot] := SLOT_RELEASE;
        END_IF
    ELSIF aPubState[uiSlot] = SLOT_RELEASE THEN
        aPubState[uiSlot] := SLOT_FREE;
    END_IF
END_FOR

fbSubscriber(Subscribe := xSubscribe AND IsConnected(), Topic := ADR(sSubFilter), QoSSubscribe := eSubQos,
             ExpectingString := FALSE);
IF fbSubscriber.Recived AND uiRxCount < RX_MAX AND fbSubscriber.TopicOut <> 0 AND fbSubscriber.Payload <> 0 THEN
    uiRxCount := uiRxCount + 1;
    aRxTopic[uiRxCount] := fbSubscriber.TopicOut^;
    udiLen := fbSubscriber.PayloadSize;
    aRxTruncated[uiRxCount] := udiLen > GVL_Const.MQTT_CMD_PAYLOAD_LEN;
    IF udiLen > GVL_Const.MQTT_CMD_PAYLOAD_LEN THEN
        udiLen := GVL_Const.MQTT_CMD_PAYLOAD_LEN;
    END_IF
    pSrc := fbSubscriber.Payload;
    uiIdx := 0;
    WHILE uiIdx < UDINT_TO_UINT(udiLen) DO
        aRxPayload[uiRxCount][uiIdx] := (pSrc + uiIdx)^;
        uiIdx := uiIdx + 1;
    END_WHILE
    aRxPayload[uiRxCount][uiIdx] := 0;
END_IF
