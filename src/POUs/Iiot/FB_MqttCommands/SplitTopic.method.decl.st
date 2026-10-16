// Разобрать sRxTopic вида <prefix>/<DEVICE>/cmd/<Command> в sTopicDevice и sTopicCommand. FALSE — топик не
// своей станции или уровни не по шаблонам ([A-Z][A-Z0-9_]{0,15} и [A-Za-z][A-Za-z0-9_]{0,31}).
METHOD PRIVATE SplitTopic : BOOL
VAR
    iPrefixLen : INT;
    sRest : STRING(GVL_Const.MQTT_TOPIC_LEN);
    sTail : STRING(GVL_Const.MQTT_TOPIC_LEN);
    iSlash : INT;
END_VAR
