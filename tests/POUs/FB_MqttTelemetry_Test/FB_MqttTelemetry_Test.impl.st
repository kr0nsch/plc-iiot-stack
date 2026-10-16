// Каждый тест-метод вызывается каждый цикл; coUnit отслеживает завершённые (TEST_FINISHED).
PublishesAllAfterBirthWithExactJson();
WaitsForBirthAndClock();
DeadbandAndMinInterval();
QualityChangeIsImmediate();
IntegerAnyChangeAndPeriodicOnly();
PeriodRepublishesAll();
BudgetLimitsPublishesPerCallRoundRobin();
RepublishesAllAfterReconnect();
ClientRefusalIsCountedAndRetried();
NegativeAndLargeValues();
NotFiniteValueSendsLastFiniteAsBad();
