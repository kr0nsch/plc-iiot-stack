// Назначение: ПЛК-часть IIoT-стека КНС-1: связь с брокером и состояние узла (FB_MqttDiag), телеметрия
//             (FB_MqttTelemetry), тревоги (FB_MqttAlarms) и шлюз команд (FB_MqttCommands) поверх переменных
//             флагмана: значения и слова тревог читает, а принятые команды пишет FB_IiotKnsMap (сгенерирован
//             из schema/). Таблицы метрик, команд и тревог — GVL_IiotMap. Клиент MQTT — itfClientOverride
//             (адаптер библиотеки, тесты) или FB_MqttClientNone. Вызывать после PRG_Devices в той же задаче.
//             Настройки — GVL_Iiot.stIiotCfg, состояние — GVL_Iiot.stIiotSts.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «PRG_Iiot и теги флагмана»
PROGRAM PRG_Iiot
VAR_INPUT
    itfClientOverride : I_MqttClient;     // адаптер библиотеки или подменный клиент; 0 — FB_MqttClientNone
END_VAR
VAR
    fbClientNone : FB_MqttClientNone;
    itfClient : I_MqttClient;
    fbMap : FB_IiotKnsMap;
    fbDiag : FB_MqttDiag;
    fbTelemetry : FB_MqttTelemetry;
    fbAlarms : FB_MqttAlarms;
    fbCommands : FB_MqttCommands;
    aPoints : ARRAY[1..GVL_IiotMap.POINT_COUNT] OF ST_IiotPoint;
    aAlarms : ARRAY[1..GVL_IiotMap.ALARM_COUNT] OF ST_IiotAlarm;
    aAlarmWords : ARRAY[1..GVL_IiotMap.ALARM_WORDS_COUNT] OF ST_IiotAlarmWords;
    aRules : ARRAY[1..GVL_IiotMap.RULE_COUNT] OF ST_IiotCmdRule;
    xInitDone : BOOL;
    ltStart : LTIME;                      // первый вызов: отсчёт uptime
    ltNow : LTIME;
    uliTs_ms : ULINT;
    xClockValid : BOOL;
    sPrefix : STRING(GVL_Const.IIOT_PREFIX_LEN);
    uiDevSeq : UINT;
    iDevResult : INT;
    diIdx : DINT;
END_VAR
VAR CONSTANT
    RTC_OK : UDINT := 0;                  // SysTimeRtcHighResGet: «нет ошибки» (ERR_OK)
    NS_PER_S : ULINT := 1000000000;
END_VAR
