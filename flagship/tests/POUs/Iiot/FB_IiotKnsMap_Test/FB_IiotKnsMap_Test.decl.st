// Назначение: тесты привязки ПЛК-части IIoT-стека к настоящим переменным флагмана КНС-1; выполняются в
//             тестовом приложении флагмана после встраивания (tools_project/flagship_embed.py): значения
//             устройств, станции и регулятора в метриках, инверсия K1, слово тревог станции, запись команд
//             в GVL_Hmi и GVL_Station, счётчик и результат команды станции, PRG_Iiot с подменным клиентом
//             (рождение, метрики тегов флагмана, команда станции до ответа accepted). Глобальные переменные
//             флагмана тест меняет и восстанавливает в том же вызове: другие наборы их не видят.
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/TEST_REPORT.md
FUNCTION_BLOCK FB_IiotKnsMap_Test EXTENDS coUnit.FB_TestSuite
VAR
    fbMap : FB_IiotKnsMap;
    aPoints : ARRAY[1..GVL_IiotMap.POINT_COUNT] OF ST_IiotPoint;
    aWords : ARRAY[1..GVL_IiotMap.ALARM_WORDS_COUNT] OF ST_IiotAlarmWords;
    aSmallPoints : ARRAY[1..2] OF ST_IiotPoint;
    aSmallWords : ARRAY[1..2] OF ST_IiotAlarmWords;
END_VAR
