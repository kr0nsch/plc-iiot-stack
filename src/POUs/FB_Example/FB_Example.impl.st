// 1. Параметры оператора ограничиваем допустимыми диапазонами из GVL_Const
rSetpointUsed_pct := F_Clamp(rValue := rSetpoint_pct,
                             rLow := GVL_Const.EXAMPLE_SP_MIN_PCT,
                             rHigh := GVL_Const.EXAMPLE_SP_MAX_PCT);
rHysteresisUsed_pct := F_Clamp(rValue := rHysteresis_pct,
                               rLow := GVL_Const.EXAMPLE_HYST_MIN_PCT,
                               rHigh := GVL_Const.EXAMPLE_HYST_MAX_PCT);

// 2. Отказ измерения фиксируем в авторежиме — только там измерение управляет выходом.
//    Защёлка: отказ держится до квитирования, даже если измерение восстановилось.
xFault := xFault OR (eMode = E_DeviceMode.Auto AND NOT xValueValid);

// 3. Выход по режимам
CASE eMode OF
    E_DeviceMode.Auto:
        IF xFault THEN
            xOut := FALSE;      // безопасное состояние до квитирования
        ELSIF rValue_pct <= rSetpointUsed_pct - rHysteresisUsed_pct THEN
            xOut := TRUE;
        ELSIF rValue_pct >= rSetpointUsed_pct THEN
            xOut := FALSE;
        END_IF
        // внутри зоны гистерезиса выход сохраняет прежнее состояние

    E_DeviceMode.Manual:
        xOut := xManualOn;

    E_DeviceMode.Local, E_DeviceMode.OutOfService:
        // местный пост управляет сам, вывод из работы — команда ПЛК снимается
        xOut := FALSE;

ELSE
    xOut := FALSE;              // неизвестное значение режима — безопасное состояние
END_CASE

// 4. Счёт включений по переднему фронту выхода; на пределе счётчик не переполняется
IF xOut AND NOT xOutPrev AND udiCount < GVL_Const.EXAMPLE_COUNT_MAX THEN
    udiCount := udiCount + 1;
END_IF
xOutPrev := xOut;
