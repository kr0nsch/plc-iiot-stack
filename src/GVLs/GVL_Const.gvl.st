// Назначение: константы ПЛК-части IIoT-стека: размеры буферов, версия схемы сообщений, топики,
//             правила шлюза команд, коды ошибок клиента MQTT, значения по умолчанию, коды символов ASCII.
//             В логике нет «магических чисел» — только имена отсюда. Контракт — docs/data_schema.md.
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
VAR_GLOBAL CONSTANT
    // --- Размеры строк, байт (без завершающего нуля) ---
    MQTT_TOPIC_LEN : UINT := 127;          // топик
    MQTT_PAYLOAD_LEN : UINT := 1023;       // исходящее сообщение
    MQTT_CMD_PAYLOAD_LEN : UINT := 511;    // входящая команда; длиннее — invalid_payload
    IIOT_PREFIX_LEN : UINT := 63;          // префикс топика site/area/unit
    IIOT_PATH_LEN : UINT := 63;            // хвост топика device/metric
    IIOT_LEVEL_LEN : UINT := 31;           // один уровень топика (site, area, unit, metric, command)
    IIOT_DEVICE_LEN : UINT := 16;          // уровень device: [A-Z][A-Z0-9_]{0,15}
    IIOT_SUFFIX_LEN : UINT := 8;           // суффикс тревоги: [A-Z][A-Z0-9]{0,7} (NOAUTO, UL1 — тревоги станции)
    IIOT_UNIT_LEN : UINT := 16;            // единица измерения (ASCII)
    IIOT_TEXT_LEN : UINT := 31;            // короткие тексты кодов (quality, reason, state)
    JSON_KEY_LEN : UINT := 31;             // ключ JSON
    JSON_STR_LEN : UINT := 64;             // строковое значение JSON (origin — до 64 символов)
    JSON_LITERAL_LEN : UINT := 7;          // литералы true, false, null
    JSON_MAX_FIELDS : UINT := 12;          // полей в разбираемом объекте команды
    BROKER_HOST_LEN : UINT := 63;
    BROKER_CLIENT_ID_LEN : UINT := 23;     // MQTT 3.1.1: идентификатор клиента до 23 байт гарантированно
    BROKER_SECRET_LEN : UINT := 63;
    BROKER_WILL_LEN : UINT := 127;         // текст LWT

    // --- Схема сообщений (docs/data_schema.md, раздел 8) ---
    IIOT_SCHEMA_VERSION : STRING(7) := '1.1';
    IIOT_SCHEMA_MAJOR : UINT := 1;          // команды другой мажорной версии — unsupported_version
    IIOT_SOURCE : STRING(15) := 'codesys';  // поле source сообщения рождения
    TS_MIN_MS : ULINT := 1577836800000;     // ts схемы: не раньше 2020-01-01T00:00:00Z
    TS_MAX_MS : ULINT := 4102444800000;     // и не позже 2100-01-01T00:00:00Z

    // --- Топики (docs/data_schema.md, раздел 2) ---
    TOPIC_SEPARATOR : STRING(1) := '/';
    TOPIC_CMD_FILTER_SUFFIX : STRING(15) := '/+/cmd/+';     // подписка <site>/<area>/<unit>/+/cmd/+
    TOPIC_CMD_LEVEL : STRING(7) := 'cmd';
    TOPIC_ACK_LEVEL : STRING(7) := 'cmd_ack';
    TOPIC_ALARM_LEVEL : STRING(7) := 'alarm';
    TOPIC_STATUS_SUFFIX : STRING(31) := '/status/connection';

    // --- Шлюз команд (docs/data_schema.md, раздел 5.1) ---
    CMD_ID_MIN_LEN : UINT := 8;              // cmd_id: [A-Za-z0-9_-]{8,36}
    CMD_ID_LEN : UINT := 36;
    CMD_ORIGIN_LEN : UINT := 64;             // origin: печатный ASCII, 1..64 символа
    CMD_HISTORY_LEN : UINT := 16;            // повтор cmd_id среди последних 16 — duplicate
    CMD_RATE_LIMIT : UINT := 10;             // не больше 10 команд ...
    CMD_RATE_WINDOW : TIME := T#10S;         // ... за 10 с — иначе rate_limited
    CMD_MAX_AGE : TIME := T#30S;             // |время ПЛК - ts| больше — expired
    CMD_DEVICE_TIMEOUT : TIME := T#3S;       // устройство не обработало команду — timeout
    CMD_MASK_MAX : LREAL := 65535.0;         // маски AckReq, ShelveReq, UnshelveReq: 0..65535
    SPEED_SP_MIN_PCT : LREAL := 0.0;         // SpeedSp по схеме: 0..100 % независимо от белого списка
    SPEED_SP_MAX_PCT : LREAL := 100.0;
    // Коды E_CmdResult plc-process-lib (API 4.1) в ответе устройства: 1 Accepted, 2…9 Rejected*; 10
    // SubstExpired и 0 None — не ответ на команду. Станция флагмана отвечает теми же кодами (PL.E_CmdResult)
    CMD_RESULT_ACCEPTED : INT := 1;
    CMD_RESULT_LAST : INT := 9;

    // --- Числа JSON ---
    JSON_REAL_DECIMALS_DEFAULT : UINT := 3;
    JSON_REAL_DECIMALS_MAX : UINT := 6;
    JSON_NUM_SCALED_MAX : LREAL := 9.0E15;   // |x| * 10^знаков не меньше — точности LREAL мало, пишется null
    JSON_MANTISSA_DIGITS_MAX : UINT := 17;   // цифр в числе команды
    JSON_EXP_DIGITS_MAX : UINT := 3;         // цифр в показателе степени
    REAL_ABS_MAX : LREAL := 3.4028234E38;    // число команды должно помещаться в REAL
    REAL_EXP_MASK : DWORD := 16#7F800000;    // биты порядка REAL: все единицы — NaN или бесконечность
    LREAL_EXP_MASK : LWORD := 16#7FF0000000000000;
    DECIMAL_BASE : ULINT := 10;
    ULINT_DIGITS_MAX : UINT := 20;           // цифр в ULINT
    HEX_DIGITS_ESCAPE : UINT := 4;           // \uXXXX
    HEX_LETTER_START : BYTE := 10;           // шестнадцатеричная цифра 10 — буква 'a'
    NIBBLE_BITS : BYTE := 4;
    NIBBLE_MASK : BYTE := 16#0F;
    HEX_BASE : UINT := 16;

    // --- Символы ASCII ---
    ASCII_NUL : BYTE := 16#00;
    ASCII_BS : BYTE := 16#08;
    ASCII_TAB : BYTE := 16#09;
    ASCII_LF : BYTE := 16#0A;
    ASCII_FF : BYTE := 16#0C;
    ASCII_CR : BYTE := 16#0D;
    ASCII_CTRL_LAST : BYTE := 16#1F;   // 0..16#1F — управляющие символы
    ASCII_SPACE : BYTE := 16#20;
    ASCII_QUOTE : BYTE := 16#22;       // "
    ASCII_PLUS : BYTE := 16#2B;        // +
    ASCII_COMMA : BYTE := 16#2C;       // ,
    ASCII_MINUS : BYTE := 16#2D;       // -
    ASCII_DOT : BYTE := 16#2E;         // .
    ASCII_SLASH : BYTE := 16#2F;       // /
    ASCII_ZERO : BYTE := 16#30;        // 0
    ASCII_NINE : BYTE := 16#39;        // 9
    ASCII_COLON : BYTE := 16#3A;       // :
    ASCII_UPPER_A : BYTE := 16#41;
    ASCII_UPPER_E : BYTE := 16#45;
    ASCII_UPPER_F : BYTE := 16#46;
    ASCII_UPPER_Z : BYTE := 16#5A;
    ASCII_LBRACKET : BYTE := 16#5B;    // [
    ASCII_BACKSLASH : BYTE := 16#5C;   // \
    ASCII_UNDERSCORE : BYTE := 16#5F;  // _
    ASCII_LOWER_A : BYTE := 16#61;
    ASCII_LOWER_B : BYTE := 16#62;
    ASCII_LOWER_E : BYTE := 16#65;
    ASCII_LOWER_F : BYTE := 16#66;
    ASCII_LOWER_N : BYTE := 16#6E;
    ASCII_LOWER_R : BYTE := 16#72;
    ASCII_LOWER_T : BYTE := 16#74;
    ASCII_LOWER_U : BYTE := 16#75;
    ASCII_LOWER_Z : BYTE := 16#7A;
    ASCII_LBRACE : BYTE := 16#7B;      // {
    ASCII_RBRACE : BYTE := 16#7D;      // }
    ASCII_TILDE : BYTE := 16#7E;       // ~ — последний печатный символ
    ASCII_LAST : BYTE := 16#7F;        // больше — не ASCII

    // --- MQTT ---
    MQTT_PORT_DEFAULT : UINT := 1883;
    // Коды ошибок уровня ФБ (отрицательные); положительные коды — от адаптера библиотеки
    MQTT_ERR_NONE : DINT := 0;
    MQTT_ERR_NO_TRANSPORT : DINT := -1;       // клиент без транспорта (FB_MqttClientNone)
    MQTT_ERR_CONNECT_TIMEOUT : DINT := -2;    // нет подключения за tConnectTimeout
    MQTT_ERR_CONNECT_REJECTED : DINT := -3;   // Connect() вернул FALSE без кода ошибки
    MQTT_ERR_CONNECTION_LOST : DINT := -4;    // связь пропала без кода ошибки
    MQTT_ERR_NO_CLOCK : DINT := -5;           // часы ПЛК не установлены: ts вне схемы, обмен не начинается

    // --- Значения по умолчанию ---
    TELEMETRY_PERIOD_DEFAULT : TIME := T#60S;   // контрольная публикация всех метрик
    TELEMETRY_MIN_INTERVAL : TIME := T#1S;      // по изменению — не чаще раза в секунду на метрику
    TELEMETRY_MAX_PER_CYCLE : UINT := 8;        // публикаций за цикл (не перегружать очередь клиента)
    ALARMS_MAX_PER_CYCLE : UINT := 4;
    CMD_MAX_PER_CYCLE : UINT := 1;              // разбираемых команд за цикл
    CONNECT_TIMEOUT_DEFAULT : TIME := T#10S;
    BACKOFF_MIN_DEFAULT : TIME := T#1S;
    BACKOFF_MAX_DEFAULT : TIME := T#60S;
    STABLE_TIME_DEFAULT : TIME := T#30S;        // после стольких секунд связи пауза снова минимальная
    FAIL_THRESHOLD_DEFAULT : UINT := 3;         // подряд неудачных подключений до статуса «отказ»
    KEEPALIVE_DEFAULT : TIME := T#30S;
END_VAR
