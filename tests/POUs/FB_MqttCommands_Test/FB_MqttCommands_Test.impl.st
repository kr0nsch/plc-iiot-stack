// Каждый тест-метод вызывается каждый цикл; coUnit отслеживает завершённые (TEST_FINISHED).
SubscribesToCommandTopicsAndResubscribes();
AcceptedStartWaitsForDeviceThenOk();
DeviceRejectedCarriesCmdResult();
DeviceSilenceIsTimeout();
SpeedSetpointIsOkAfterWrite();
MissingArmMeansTimeout();
RejectsRetainedCommand();
RejectsInvalidPayloads();
RejectsUnsupportedVersionAndTopicMismatch();
RejectsNotWhitelisted();
RejectsOutOfRange();
RejectsExpired();
RejectsDuplicateIncludingRejectedIds();
RateLimitTenPerTenSeconds();
DropsWithoutAckWhenNoCmdId();
