// Не больше uiMaxPerCycle за вызов, остальные — в следующих, по кругу.
METHOD PRIVATE BudgetLimitsPublishesPerCallRoundRobin
VAR_INST
    fbFake : FB_MqttClientFake;
    fbTel : FB_MqttTelemetry;
    aPts : ARRAY[1..5] OF ST_IiotPoint;
END_VAR
