// Назначение: адаптер I_MqttClient на библиотеку CODESYS-MQTT (github.com/stefandreyer/CODESYS-MQTT), релиз
//             «stable» (Project Information: MQTT 1.0.0.0, компания Stefan Dreyer, пространство имён SD_MQTT).
//             НЕ КОМПИЛИРОВАЛСЯ С РАБОЧЕЙ БИБЛИОТЕКОЙ: на CODESYS 3.5.17.30 у библиотеки нет зависимостей
//             (OSCAT BASIC 3.3.3.0, OSCAT NETWORK 1.30, «Common Helper for development» и системные
//             библиотеки точных версий 3.5.5–3.5.13), поэтому файл лежит вне src/ (docs/MANUAL_STEPS.md, раздел 9).
//             Сигнатуры взяты из объявлений библиотеки (HANDLE_MQTT, MQTTPublish, MQTTSubscribe, MQTT_IN_OUT).
//             Пул из PUB_POOL публикаторов: библиотека требует не менять топик и текст до done и пускает
//             публикацию по фронту send. Логин и пароль брокера версия 1.0.0.0 через входы не принимает —
//             Connect с непустым sUser отклоняется (MQTT_ERR_AUTH_UNSUPPORTED), а не подключается без пароля.
//             Завещание (LWT) версия строит сама из ClientID (WillTopicBase, ClientWillTopic, ClientWillMessage
//             до 30 символов): offline/lwt по data_schema 6 с ней не получить; флаг retain принятых сообщений
//             не виден (проверка retained шлюза команд не срабатывает).
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Адаптер I_MqttClient»
FUNCTION_BLOCK FB_MqttClientSdMqtt IMPLEMENTS I_MqttClient
VAR_INPUT
    tTimeout : TIME := T#5S;                           // HANDLE_MQTT.TIMEOUT
END_VAR
VAR
    fbHandler : SD_MQTT.HANDLE_MQTT;
    stInOut : SD_MQTT.MQTT_IN_OUT;
    stInfo : SD_MQTT.MQTT_INFO;
    aPublishers : ARRAY[1..PUB_POOL] OF SD_MQTT.MQTTPublish;
    aPubTopic : ARRAY[1..PUB_POOL] OF STRING(GVL_Const.MQTT_TOPIC_LEN);
    aPubPayload : ARRAY[1..PUB_POOL] OF STRING(GVL_Const.MQTT_PAYLOAD_LEN);
    aPubLen : ARRAY[1..PUB_POOL] OF UDINT;
    aPubQos : ARRAY[1..PUB_POOL] OF SD_MQTT.QoS;
    aPubRetain : ARRAY[1..PUB_POOL] OF BOOL;
    aPubState : ARRAY[1..PUB_POOL] OF USINT;          // SLOT_FREE, SLOT_SENDING, SLOT_RELEASE
    fbSubscriber : SD_MQTT.MQTTSubscribe;
    sSubFilter : STRING(GVL_Const.MQTT_TOPIC_LEN);
    eSubQos : SD_MQTT.QoS;
    xSubscribe : BOOL;
    aRxTopic : ARRAY[1..RX_MAX] OF STRING(GVL_Const.MQTT_TOPIC_LEN);
    aRxPayload : ARRAY[1..RX_MAX] OF STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
    aRxTruncated : ARRAY[1..RX_MAX] OF BOOL;
    uiRxCount : UINT;
    sUrl : STRING(GVL_Const.MQTT_TOPIC_LEN);
    xEnable : BOOL;
    xTls : BOOL;
    xBound : BOOL;                                     // SetMqttInOut выполнен у всех ФБ библиотеки
    diError : DINT;
    uiSlot : UINT;
END_VAR
VAR CONSTANT
    PUB_POOL : UINT := 8;
    RX_MAX : UINT := 8;
    SLOT_FREE : USINT := 0;
    SLOT_SENDING : USINT := 1;     // send = TRUE до done или SendTimeout
    SLOT_RELEASE : USINT := 2;     // один вызов с send = FALSE, чтобы следующий фронт был виден
    MQTT_ERR_AUTH_UNSUPPORTED : DINT := -10;
    MQTT_ERR_SEND_TIMEOUT : DINT := -11;
END_VAR
