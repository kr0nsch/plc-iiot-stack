// Назначение: публикация событий тревог (data_schema 4) в <prefix>/<device>/alarm/<suffix>, QoS 1, retain:
//             {schema_version, ts, id, code, priority, state, prev_state, reason}. Состояние тревоги — по
//             словам устройства (wAlmActive, wAlmUnack, wAlmShelved, режим OutOfService); событие — смена
//             состояния с прошлой публикации, причина — по переходу (F_IiotAlarmReason). После каждого
//             рождения узла (xReady) публикуются все тревоги: не менявшаяся — повтором последней
//             публикации с её ts (в InfluxDB та же точка, не новое срабатывание), изменившаяся без связи —
//             событием, ещё не публиковавшаяся с запуска ПЛК — снимком (prev_state = state). Переходы между
//             двумя публикациями сливаются в один; точные события ST_AlarmEvent во флагмане даёт
//             PL.I_AlarmSink (docs/plc_mqtt.md).
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.1
// Документ:   docs/plc_mqtt.md, раздел «Тревоги»
FUNCTION_BLOCK FB_MqttAlarms
VAR_INPUT
    xEnable : BOOL;
    xReady : BOOL;                                        // связь есть и рождение опубликовано
    itfClient : I_MqttClient;
    uliTs_ms : ULINT;                                     // время UTC, мс (поле ts)
    sTopicPrefix : STRING(GVL_Const.IIOT_PREFIX_LEN);     // site/area/unit
    uiMaxPerCycle : UINT := GVL_Const.ALARMS_MAX_PER_CYCLE;
END_VAR
VAR_IN_OUT
    aAlarms : ARRAY[*] OF ST_IiotAlarm;
    aWords : ARRAY[*] OF ST_IiotAlarmWords;               // строки — ST_IiotAlarmCfg.diWords
END_VAR
VAR_OUTPUT
    udiPublished : UDINT;
    udiFailed : UDINT;
    udiDropped : UDINT;
    udiEvents : UDINT;          // опубликовано событий (без снимков)
    uiPending : UINT;
END_VAR
VAR
    fbJson : FB_JsonBuilder;
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
    diCursor : DINT;
END_VAR
