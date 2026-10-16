// Подписка <site>/<area>/<unit>/+/cmd/+ с QoS 1; заново после переподключения.
METHOD PRIVATE SubscribesToCommandTopicsAndResubscribes
VAR_INST
    fbFake : FB_MqttClientFake;
    fbCmd : FB_MqttCommands;
    aRules : ARRAY[1..4] OF ST_IiotCmdRule;
END_VAR
