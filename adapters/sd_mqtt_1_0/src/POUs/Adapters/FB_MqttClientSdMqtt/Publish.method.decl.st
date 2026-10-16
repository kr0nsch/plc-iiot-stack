// Занять свободный публикатор пула: копия топика и текста (библиотека читает их до done).
METHOD Publish : BOOL
VAR_INPUT
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
    eQos : E_MqttQos;
    xRetain : BOOL;
END_VAR
VAR_IN_OUT CONSTANT
    // lint:allow STL007 параметр VAR_IN_OUT CONSTANT — ссылка только для чтения, а не константа
    sPayload : STRING(GVL_Const.MQTT_PAYLOAD_LEN);
END_VAR
VAR
    uiLen : UINT;
END_VAR
