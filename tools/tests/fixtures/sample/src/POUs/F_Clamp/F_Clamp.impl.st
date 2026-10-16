// При перепутанных границах возвращаем нижнюю — безопасное значение
IF rMin > rMax THEN
    F_Clamp := rMin;
ELSE
    F_Clamp := LIMIT(rMin, rValue, rMax);
END_IF
