// PRG_Iiot с подменным клиентом в приложении флагмана: рождение, метрики тегов флагмана, команда станции
// SetStepped через GVL_Station.stStationCmd до ответа accepted, команда вне белого списка.
METHOD PRIVATE PrgIiotPublishesAndAppliesStationCommand
VAR_INST
    fbFake : FB_MqttClientFake;
    xRan : BOOL;              // тест длинный: выполняется один раз, дальше coUnit только вызывает метод
END_VAR
VAR
    iCall : INT;
    uliNow : ULINT;
    stCmdSaved : ST_StationCmd;
    stStsSaved : ST_StationSts;
    xK1Saved : BOOL;
    sCmd : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
END_VAR
