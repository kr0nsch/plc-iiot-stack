// Назначение: программа запуска юнит-тестов CfUnit (coUnit 1.2.0.0). Объявляет
//             экземпляры наборов тестов (объявление регистрирует набор в coUnit)
//             и каждый цикл вызывает coUnit.RUN(). Назначается задаче только
//             тестового приложения (CODESYS Control Win), не рабочего ПЛК.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/TEST_REPORT.md
PROGRAM PRG_Tests
VAR
    fbF_ClampTest : FB_F_Clamp_Test;    // тесты F_Clamp
    fbExampleTest : FB_Example_Test;    // тесты FB_Example
    // все наборы завершены — флаг для скрипта запуска тестов (read_value)
    xAllFinished : BOOL;
END_VAR
