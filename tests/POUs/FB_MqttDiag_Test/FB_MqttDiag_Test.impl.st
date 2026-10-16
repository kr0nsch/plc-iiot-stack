// Каждый тест-метод вызывается каждый цикл; coUnit отслеживает завершённые (TEST_FINISHED).
DisabledIsCheckFunctionWithoutConnect();
ConnectSetsLwtAndPublishesBirth();
BirthRefusedMeansNotReady();
NoClockNoConnect();
ConnectTimeoutGoesToBackoff();
BackoffDoublesUpToMaximum();
RejectedConnectUsesClientErrorCode();
FailureAfterThresholdAndResetAfterStableLink();
ConnectionLossCountsAndReconnects();
DegradedWhenPublishFailuresGrow();
DisableWhileConnectedPublishesShutdown();
TimeGoingBackwardsRestartsTimeout();
