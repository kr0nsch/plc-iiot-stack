// Упорядочиваем границы: при rLow > rHigh меняем их местами
IF rLow <= rHigh THEN
    rMin := rLow;
    rMax := rHigh;
ELSE
    rMin := rHigh;
    rMax := rLow;
END_IF

// Ограничиваем значение; на границе возвращается сама граница
IF rValue < rMin THEN
    F_Clamp := rMin;
ELSIF rValue > rMax THEN
    F_Clamp := rMax;
ELSE
    F_Clamp := rValue;
END_IF
