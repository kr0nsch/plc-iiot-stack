// Назначение: клиент MQTT без транспорта: подключение всегда отклоняется (LastError = MQTT_ERR_NO_TRANSPORT),
//             публикации и подписки не принимаются. Используется, пока в проект не добавлен адаптер
//             библиотеки CODESYS-MQTT (docs/MANUAL_STEPS.md): логика и диагностика работают, FB_MqttDiag
//             честно показывает отсутствие связи.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Адаптер I_MqttClient»
FUNCTION_BLOCK FB_MqttClientNone IMPLEMENTS I_MqttClient
