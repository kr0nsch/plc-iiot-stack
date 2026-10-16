// Четыре метрики: уровень (Analog, зона 0.01 м), работа насоса (Integer), пуски (Integer), время работы узла
// (только контрольно); связь есть.
METHOD PRIVATE Setup
VAR_IN_OUT
    fbClient : FB_MqttClientFake;
    aPointTable : ARRAY[1..4] OF ST_IiotPoint;
END_VAR
