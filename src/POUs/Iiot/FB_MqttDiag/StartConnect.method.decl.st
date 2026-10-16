// Завещание offline/lwt со временем подключения в параметрах брокера и запрос подключения; отказ клиента —
// неудачная попытка.
METHOD PRIVATE StartConnect
VAR_IN_OUT
    stBrokerCfg : ST_MqttBrokerCfg;
END_VAR
