// Назначение: константы проекта. В логике нет «магических чисел» — только имена отсюда.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/ARCHITECTURE.md, раздел «Пример в src/»
{attribute 'qualified_only'}
VAR_GLOBAL CONSTANT
    // Пример FB_Example: допустимый диапазон уставки, % диапазона датчика
    EXAMPLE_SP_MIN_PCT : REAL := 0.0;
    EXAMPLE_SP_MAX_PCT : REAL := 100.0;
    EXAMPLE_SP_DEFAULT_PCT : REAL := 50.0;

    // Пример FB_Example: допустимый гистерезис, %. Нижняя граница защищает выход
    // от частых переключений при шуме измерения.
    EXAMPLE_HYST_MIN_PCT : REAL := 0.5;
    EXAMPLE_HYST_MAX_PCT : REAL := 20.0;
    EXAMPLE_HYST_DEFAULT_PCT : REAL := 5.0;

    // Предел счётчика включений: максимум UDINT, дальше счётчик не растёт (насыщение)
    EXAMPLE_COUNT_MAX : UDINT := 4294967295;
END_VAR
