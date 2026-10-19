// Назначение: программа запуска юнит-тестов CfUnit (coUnit 1.2.0.0): объявляет экземпляры наборов
//             (объявление регистрирует набор в coUnit) и каждый цикл вызывает coUnit.RUN(). Назначается
//             задаче только тестового приложения (CODESYS Control Win), не рабочего ПЛК.
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/TEST_REPORT.md
PROGRAM PRG_Tests
VAR
    fbJsonBuilderTest : FB_JsonBuilder_Test;
    fbJsonFlatParserTest : FB_JsonFlatParser_Test;
    fbIiotFunctionsTest : FB_IiotFunctions_Test;
    fbMqttTelemetryTest : FB_MqttTelemetry_Test;
    fbMqttAlarmsTest : FB_MqttAlarms_Test;
    fbMqttCommandsTest : FB_MqttCommands_Test;
    fbMqttDiagTest : FB_MqttDiag_Test;
    fbIiotMapTest : FB_IiotMap_Test;
    // все наборы завершены — флаг для скрипта запуска тестов (read_value)
    xAllFinished : BOOL;
END_VAR
