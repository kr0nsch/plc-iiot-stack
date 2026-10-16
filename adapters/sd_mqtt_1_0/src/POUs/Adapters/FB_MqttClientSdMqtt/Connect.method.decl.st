// Адрес host:port, идентификатор клиента, TLS; логин и пароль не поддерживаются (см. заголовок).
METHOD Connect : BOOL
VAR_IN_OUT CONSTANT
    // lint:allow STL007 параметр VAR_IN_OUT CONSTANT — ссылка только для чтения, а не константа
    stCfg : ST_MqttBrokerCfg;
END_VAR
