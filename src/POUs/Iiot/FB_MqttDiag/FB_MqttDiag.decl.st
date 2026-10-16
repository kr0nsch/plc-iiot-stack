// Назначение: ведение связи с брокером и состояние узла (data_schema 6): автомат Disabled -> Connecting ->
//             Connected -> Backoff -> Connecting; тайм-аут подключения, пауза между попытками удваивается от
//             tBackoffMin до tBackoffMax и снова минимальна после tStable устойчивой связи. Перед Connect —
//             завещание (LWT) в <prefix>/<sNode>/status/connection: offline/lwt со временем подключения;
//             после подключения — рождение online/birth (source, sw_version, period_ms), затем xReady.
//             Выключение при связи — offline/shutdown, разрыв в следующем вызове. Без часов ПЛК обмен не
//             начинается (MQTT_ERR_NO_CLOCK). Счётчики, код последней ошибки, сводный статус в духе NE 107.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Связь и состояние узла»
FUNCTION_BLOCK FB_MqttDiag
VAR_INPUT
    xEnable : BOOL;
    itfClient : I_MqttClient;
    ltNow : LTIME;                                            // монотонное время (LTIME())
    uliTs_ms : ULINT;                                         // время UTC, мс (поле ts)
    sTopicPrefix : STRING(GVL_Const.IIOT_PREFIX_LEN);         // site/area/unit
    sNode : STRING(GVL_Const.IIOT_DEVICE_LEN) := 'PLC1';
    sSwVersion : STRING(GVL_Const.IIOT_TEXT_LEN) := '0.1.0';
    tPeriod : TIME := GVL_Const.TELEMETRY_PERIOD_DEFAULT;    // период контрольной публикации (period_ms)
    tConnectTimeout : TIME := GVL_Const.CONNECT_TIMEOUT_DEFAULT;
    tBackoffMin : TIME := GVL_Const.BACKOFF_MIN_DEFAULT;
    tBackoffMax : TIME := GVL_Const.BACKOFF_MAX_DEFAULT;
    tStable : TIME := GVL_Const.STABLE_TIME_DEFAULT;
    tDegradeWindow : TIME := GVL_Const.TELEMETRY_PERIOD_DEFAULT;   // окно оценки отказов публикаций
    uiFailThreshold : UINT := GVL_Const.FAIL_THRESHOLD_DEFAULT;
    udiPubFailed : UDINT;                                     // отказы публикаций телеметрии и тревог
END_VAR
VAR_IN_OUT
    stBroker : ST_MqttBrokerCfg;                              // ФБ дописывает топик и текст LWT
END_VAR
VAR_OUTPUT
    eState : E_MqttConnState := E_MqttConnState.Disabled;
    eNe107 : E_IiotNe107 := E_IiotNe107.CheckFunction;
    xConnected : BOOL;
    xReady : BOOL;                  // связь есть и рождение опубликовано: можно публиковать
    udiConnects : UDINT;            // успешных подключений
    udiDisconnects : UDINT;         // потерь установленной связи
    udiConnectFailures : UDINT;     // неудачных попыток подключения
    uiConsecutiveFailures : UINT;   // неудачных попыток подряд (сброс после tStable связи)
    diLastError : DINT;             // GVL_Const.MQTT_ERR_* или код библиотеки
    tBackoff : TIME;                // пауза перед следующей попыткой
    xDegraded : BOOL;               // за последнее окно публикации отклонялись
END_VAR
VAR
    ltStateSince : LTIME;
    ltDegradeStart : LTIME;
    udiPubFailedRef : UDINT;
    fbJson : FB_JsonBuilder;
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
END_VAR
