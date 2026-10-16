// Все зарегистрированные наборы выполняются параллельно; итоги — в журнал
// устройства (логгер coUnit) и в XML-файл xUnit
coUnit.RUN();

// AreAllTestsFinished() вызывается после RUN(): у метода есть побочный эффект
// на первом цикле. Наборы объединяются через AND (не AND_THEN): метод вызывается
// у каждого набора в каждом цикле.
xAllFinished := fbF_ClampTest.AreAllTestsFinished() AND fbExampleTest.AreAllTestsFinished();
