IF LEN(sPrefix) = 0 THEN
    F_IiotTopic := sPath;
ELSIF LEN(sPrefix) + LEN(GVL_Const.TOPIC_SEPARATOR) + LEN(sPath) > UINT_TO_INT(GVL_Const.MQTT_TOPIC_LEN) THEN
    F_IiotTopic := '';
ELSE
    F_IiotTopic := CONCAT(CONCAT(sPrefix, GVL_Const.TOPIC_SEPARATOR), sPath);
END_IF
