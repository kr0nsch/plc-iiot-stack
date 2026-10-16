// Все зарегистрированные наборы выполняются параллельно; итоги — в журнал устройства и в XML xUnit
coUnit.RUN();

// AreAllTestsFinished() — после RUN(); наборы объединяются через AND (не AND_THEN): метод вызывается
// у каждого набора в каждом цикле.
xAllFinished := fbJsonBuilderTest.AreAllTestsFinished()
    AND fbJsonFlatParserTest.AreAllTestsFinished()
    AND fbIiotFunctionsTest.AreAllTestsFinished()
    AND fbMqttTelemetryTest.AreAllTestsFinished()
    AND fbMqttAlarmsTest.AreAllTestsFinished()
    AND fbMqttCommandsTest.AreAllTestsFinished()
    AND fbMqttDiagTest.AreAllTestsFinished()
    AND fbKnsShimTest.AreAllTestsFinished();
