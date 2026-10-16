// PRG_Iiot с подменным клиентом: рождение, метрики и тревоги тегов флагмана, команда до ответа ok.
METHOD PRIVATE PrgIiotPublishesFlagshipTagsAndAppliesCommands
VAR_INST
    fbFake : FB_MqttClientFake;
    xRan : BOOL;              // тест длинный: выполняется один раз, дальше coUnit только вызывает метод
END_VAR
VAR
    iCall : INT;
    uliNow : ULINT;
    uiSeq0 : UINT;
    sCmd : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
