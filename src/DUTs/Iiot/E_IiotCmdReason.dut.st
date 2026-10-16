// Назначение: причина в ответе на команду (поле reason, data_schema 5.1).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_IiotCmdReason :
(
    Ok := 0,   // 'ok': принята (result = accepted)
    NotWhitelisted := 1,   // 'not_whitelisted': пары (устройство, команда) нет в белом списке
    OutOfRange := 2,   // 'out_of_range': value вне [min; max]
    InvalidPayload := 3,   // 'invalid_payload': не по command.schema.json
    UnsupportedVersion := 4,   // 'unsupported_version': мажорная версия не 1
    TopicMismatch := 5,   // 'topic_mismatch': command в теле не совпадает с топиком
    Retained := 6,   // 'retained': сообщение с флагом retain
    Expired := 7,   // 'expired': ts дальше допуска от часов ПЛК (или часов нет)
    Duplicate := 8,   // 'duplicate': cmd_id среди последних 16
    RateLimited := 9,   // 'rate_limited': больше 10 команд за 10 с
    DeviceRejected := 10,   // 'device_rejected': устройство отказало (cmd_result)
    Timeout := 11   // 'timeout': устройство не обработало команду
) INT;
END_TYPE
