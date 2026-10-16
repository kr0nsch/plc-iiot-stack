// Сохранять ли сообщение: фильтр aCapture пуст или топик в нём.
METHOD PRIVATE Captured : BOOL
VAR_INPUT
    sTopicIn : STRING(GVL_Const.MQTT_TOPIC_LEN);
END_VAR
VAR
    uiIdx : UINT;
    xAny : BOOL;
END_VAR
