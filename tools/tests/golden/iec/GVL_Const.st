{attribute 'qualified_only'}
// Константы проекта: в логике нет «магических чисел»
VAR_GLOBAL CONSTANT
    MOTOR_START_TIMEOUT : TIME := T#5S;     // ожидание обратной связи при пуске
    MOTOR_SPEED_MAX_RPM : REAL := 1500.0;   // верхняя граница уставки
    MOTOR_SPEED_MIN_RPM : REAL := 0.0;      // нижняя граница уставки
    STEP_IDLE : INT := 0;
    STEP_RUN : INT := 10;
END_VAR
