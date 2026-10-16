// Назначение: публикация телеметрии (data_schema 3): одна метрика — один топик <prefix>/<device>/<metric>,
//             JSON {schema_version, ts, value, quality, unit}, QoS 1, retain. По изменению: Analog — когда
//             значение ушло от опубликованного больше зоны нечувствительности, Integer — при любом изменении
//             (зона 0), не чаще tMinInterval на метрику; смена quality — сразу. Контрольная публикация всех
//             метрик — раз в tPeriod и после каждого рождения узла (xReady). За вызов — не больше
//             uiMaxPerCycle публикаций, обход по кругу: ни одна метрика не ждёт вечно.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.1
// Документ:   docs/plc_mqtt.md, раздел «Телеметрия»
FUNCTION_BLOCK FB_MqttTelemetry
VAR_INPUT
    xEnable : BOOL;
    xReady : BOOL;                                           // связь есть и рождение опубликовано (FB_MqttDiag)
    itfClient : I_MqttClient;
    ltNow : LTIME;                                           // монотонное время (LTIME())
    uliTs_ms : ULINT;                                        // время UTC, мс от 1970 (поле ts)
    sTopicPrefix : STRING(GVL_Const.IIOT_PREFIX_LEN);        // site/area/unit
    tPeriod : TIME := GVL_Const.TELEMETRY_PERIOD_DEFAULT;   // T#0S — без контрольной публикации
    tMinInterval : TIME := GVL_Const.TELEMETRY_MIN_INTERVAL;
    uiMaxPerCycle : UINT := GVL_Const.TELEMETRY_MAX_PER_CYCLE;
END_VAR
VAR_IN_OUT
    aPoints : ARRAY[*] OF ST_IiotPoint;
END_VAR
VAR_OUTPUT
    udiPublished : UDINT;       // принято клиентом
    udiFailed : UDINT;          // клиент не принял (нет места в очереди): метрика повторится
    udiDropped : UDINT;         // JSON или топик не поместились: метрика пропущена
    uiPending : UINT;           // метрик ждут публикации после этого вызова
END_VAR
VAR
    fbJson : FB_JsonBuilder;
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
    xPeriodRunning : BOOL;
    ltPeriodStart : LTIME;
    diCursor : DINT;            // с какой метрики начинать обход в следующем вызове
END_VAR
