sTopic := F_IiotTopic(sPrefix := sTopicPrefix, sPath := stPoint.stCfg.sPath);
xFinite := F_IsFiniteLreal(lrValue := stPoint.lrValue);
IF xFinite THEN
    lrOut := stPoint.lrValue;
    eOutQuality := stPoint.eQuality;
ELSE
    lrOut := stPoint.lrLastFinite;
    eOutQuality := E_IiotQuality.Bad;
END_IF
fbJson.Begin();
fbJson.AddString(sKey := 'schema_version', sValue := GVL_Const.IIOT_SCHEMA_VERSION);
fbJson.AddInt(sKey := 'ts', liValue := ULINT_TO_LINT(uliTs_ms));
IF stPoint.stCfg.eKind = E_IiotValueKind.Analog THEN
    fbJson.AddReal(sKey := 'value', lrValue := lrOut, uiDecimals := stPoint.stCfg.uiDecimals);
ELSE
    fbJson.AddInt(sKey := 'value', liValue := LREAL_TO_LINT(lrOut));
END_IF
fbJson.AddString(sKey := 'quality', sValue := F_IiotQualityText(eQuality := eOutQuality));
IF LEN(stPoint.stCfg.sUnit) > 0 THEN
    fbJson.AddString(sKey := 'unit', sValue := stPoint.stCfg.sUnit);
END_IF

IF NOT fbJson.Finish() OR LEN(sTopic) = 0 THEN
    udiDropped := udiDropped + 1;     // повторять бессмысленно: размер не изменится
ELSIF itfClient.Publish(sTopic := sTopic, eQos := E_MqttQos.AtLeastOnce, xRetain := TRUE,
                        sPayload := fbJson.sJson) THEN
    udiPublished := udiPublished + 1;
ELSE
    udiFailed := udiFailed + 1;
    RETURN;
END_IF
stPoint.lrLastValue := stPoint.lrValue;
IF xFinite THEN
    stPoint.lrLastFinite := stPoint.lrValue;
END_IF
stPoint.eLastQuality := stPoint.eQuality;
stPoint.ltLastSent := ltNow;
stPoint.xSent := TRUE;
stPoint.xForce := FALSE;
PublishPoint := TRUE;
