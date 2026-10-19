// Назначение: подменный клиент MQTT для тестов (I_MqttClient): связь, отказы подключения, подписки и
//             публикации задаются входами; опубликованные сообщения сохраняются (aPub; фильтр aCapture —
//             только нужные топики), входящие ставятся в очередь методом Inject. Методы поиска по топику
//             безопасны для пустого журнала.
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/TEST_REPORT.md
FUNCTION_BLOCK FB_MqttClientFake IMPLEMENTS I_MqttClient
VAR_INPUT
    xLinkUp : BOOL := TRUE;            // брокер доступен: после Connect связь есть сразу
    xConnectAccepts : BOOL := TRUE;    // Connect() возвращает TRUE
    xSubscribeAccepts : BOOL := TRUE;
    xPublishAccepts : BOOL := TRUE;    // FALSE — «очередь полна»
    diError : DINT;                    // значение LastError()
    aCapture : ARRAY[1..CAPTURE_MAX] OF STRING(GVL_Const.MQTT_TOPIC_LEN);   // не пусто — сохранять только эти
END_VAR
VAR_OUTPUT
    xConnectRequested : BOOL;
    uiConnectCalls : UINT;
    uiDisconnectCalls : UINT;
    uiServiceCalls : UINT;
    uiSubscribeCalls : UINT;
    stLastCfg : ST_MqttBrokerCfg;
    sLastFilter : STRING(GVL_Const.MQTT_TOPIC_LEN);
    eLastFilterQos : E_MqttQos;
    uiPubCount : UINT;                 // сообщений в aPub
    uiPubTotal : UINT;                 // принятых публикаций всего (сохранённых и нет)
    uiPubRejected : UINT;              // Publish вернул FALSE
    aPub : ARRAY[1..PUB_MAX] OF ST_FakeMqttMsg;
    uiInCount : UINT;                  // входящих в очереди
END_VAR
VAR
    aIn : ARRAY[1..IN_MAX] OF ST_FakeMqttIn;
END_VAR
VAR CONSTANT
    PUB_MAX : UINT := 48;
    IN_MAX : UINT := 16;
    CAPTURE_MAX : UINT := 8;
END_VAR
