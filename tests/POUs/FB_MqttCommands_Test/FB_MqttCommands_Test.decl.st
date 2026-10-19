// Назначение: тесты FB_MqttCommands с подменным клиентом: подписка, ожидание устройства и
//             ответы ok, device_rejected, timeout, команды-значения, каждая причина отказа шлюза по порядку
//             data_schema 5.1, частота, повторы, сообщения без ответа.
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/TEST_REPORT.md
FUNCTION_BLOCK FB_MqttCommands_Test EXTENDS coUnit.FB_TestSuite
