IF NOT IsConnected() THEN
    RETURN;
END_IF
FOR uiSlot := 1 TO PUB_POOL DO
    IF aPubState[uiSlot] = SLOT_FREE THEN
        uiLen := 0;
        WHILE uiLen < GVL_Const.MQTT_PAYLOAD_LEN AND_THEN sPayload[uiLen] <> 0 DO
            uiLen := uiLen + 1;
        END_WHILE
        aPubTopic[uiSlot] := sTopic;
        aPubPayload[uiSlot] := sPayload;
        aPubLen[uiSlot] := UINT_TO_UDINT(uiLen);
        aPubQos[uiSlot] := ToLibQos(eQosIn := eQos);
        aPubRetain[uiSlot] := xRetain;
        aPubState[uiSlot] := SLOT_SENDING;
        Publish := TRUE;
        RETURN;
    END_IF
END_FOR
