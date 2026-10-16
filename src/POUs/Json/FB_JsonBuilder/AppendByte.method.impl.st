IF uiLen >= GVL_Const.MQTT_PAYLOAD_LEN THEN
    xOverflow := TRUE;
    RETURN;
END_IF
sJson[uiLen] := bChar;
uiLen := uiLen + 1;
sJson[uiLen] := GVL_Const.ASCII_NUL;
