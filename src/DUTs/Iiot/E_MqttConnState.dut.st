// Назначение: состояние связи с брокером (FB_MqttDiag).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_MqttConnState :
(
    Disabled := 0,   // обмен выключен (xEnable = FALSE) или нет часов
    Connecting := 1,   // подключение запрошено, ждём
    Connected := 2,   // связь есть
    Backoff := 3,   // пауза перед повторным подключением
    Closing := 4   // штатное отключение: опубликовано offline/shutdown, следующий вызов — разрыв
) INT;
END_TYPE
