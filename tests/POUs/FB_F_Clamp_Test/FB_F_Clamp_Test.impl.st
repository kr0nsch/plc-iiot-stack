// Каждый тест-метод вызывается каждый цикл; coUnit сам отслеживает, какие тесты
// завершены (TEST_FINISHED), и собирает результаты. Сам набор вызывает раннер coUnit.
InsideRangeReturnsValue();
BelowLowReturnsLow();
AboveHighReturnsHigh();
AtLowBoundaryReturnsLow();
AtHighBoundaryReturnsHigh();
EqualBoundsReturnsBound();
LowGreaterThanHighSwapsBounds();
