// Назначение: шлюз команд MQTT (data_schema 5): подписка <prefix>/+/cmd/+ (QoS 1), разбор подмножества JSON,
//             проверки по порядку раздела 5.1 (retained, invalid_payload, unsupported_version, topic_mismatch,
//             not_whitelisted, out_of_range, expired, duplicate, rate_limited) и ответ в
//             <prefix>/<device>/cmd_ack/<command>. Сообщение не своей станции или без читаемого cmd_id —
//             без ответа (udiDropped). Прошедшая команда — импульс xCmdValid и stCmd: вызывающий пишет её в
//             GVL_Hmi и вызывает Arm(); дальше ФБ ждёт, пока устройство увеличит uiCmdSeq (ok или
//             device_rejected по eCmdResult), иначе через tDeviceTimeout — timeout. Значения (SpeedSp) ФБ
//             устройства не квитирует: ok — сразу после записи. Одна команда в обработке за раз.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Команды»
FUNCTION_BLOCK FB_MqttCommands
VAR_INPUT
    xEnable : BOOL;
    itfClient : I_MqttClient;
    ltNow : LTIME;                                            // монотонное время (LTIME())
    uliTs_ms : ULINT;                                         // время UTC, мс: проверка ts и поле ts ответа
    sTopicPrefix : STRING(GVL_Const.IIOT_PREFIX_LEN);         // site/area/unit
    uiDevSeq : UINT;                                          // uiCmdSeq устройства команды в обработке
    iDevResult : INT;                                         // eCmdResult того же устройства
    tMaxAge : TIME := GVL_Const.CMD_MAX_AGE;
    tDeviceTimeout : TIME := GVL_Const.CMD_DEVICE_TIMEOUT;
    uiRateLimit : UINT := GVL_Const.CMD_RATE_LIMIT;           // не больше CMD_RATE_LIMIT
    tRateWindow : TIME := GVL_Const.CMD_RATE_WINDOW;
    uiMaxPerCycle : UINT := GVL_Const.CMD_MAX_PER_CYCLE;
END_VAR
VAR_IN_OUT
    aRules : ARRAY[*] OF ST_IiotCmdRule;                      // белый список
END_VAR
VAR_OUTPUT
    xCmdValid : BOOL;                                         // в этом вызове: записать stCmd в GVL_Hmi, затем Arm()
    stCmd : ST_IiotCmd;
    xPending : BOOL;                                          // ждём обработки устройством
    xSubscribed : BOOL;
    eLastReason : E_IiotCmdReason := E_IiotCmdReason.Ok;
    udiReceived : UDINT;
    udiAccepted : UDINT;                                      // ответов ok
    udiRejected : UDINT;                                      // ответов с отказом
    udiDropped : UDINT;                                       // без ответа: чужой топик, нет cmd_id
    udiAckFailed : UDINT;                                     // ответ не принят клиентом или не помещается
END_VAR
VAR
    fbParser : FB_JsonFlatParser;
    fbJson : FB_JsonBuilder;
    sFilter : STRING(GVL_Const.MQTT_TOPIC_LEN);
    sRxTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
    sRxPayload : STRING(GVL_Const.MQTT_CMD_PAYLOAD_LEN);
    xRxTruncated : BOOL;
    xRxRetained : BOOL;
    sAckTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
    // команда, на которую готовится ответ
    sTopicDevice : STRING(GVL_Const.IIOT_LEVEL_LEN);
    sTopicCommand : STRING(GVL_Const.IIOT_LEVEL_LEN);
    sCmdId : STRING(GVL_Const.JSON_STR_LEN);
    // повторы и частота
    aHistory : ARRAY[1..GVL_Const.CMD_HISTORY_LEN] OF STRING(GVL_Const.CMD_ID_LEN);
    uiHistoryNext : UINT := 1;
    aRateTimes : ARRAY[1..GVL_Const.CMD_RATE_LIMIT] OF LTIME;   // моменты последних прошедших команд
    uiRateNext : UINT := 1;
    uiRateCount : UINT;
    // обработка устройством
    xAwaitArm : BOOL;
    uiSeqArmed : UINT;
    ltPendingSince : LTIME;
    uiMsg : UINT;
END_VAR
