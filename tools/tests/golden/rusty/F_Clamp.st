(*
    Назначение: ограничение значения диапазоном [rMin, rMax]
    Автор: kr0nsch
    Версия: 1.0.0
    Документ: docs/ARCHITECTURE.md
*)
FUNCTION F_Clamp : REAL
VAR_INPUT
    rValue : REAL;  // входное значение
    rMin : REAL;    // нижняя граница
    rMax : REAL;    // верхняя граница
END_VAR
// При перепутанных границах возвращаем нижнюю — безопасное значение
IF rMin > rMax THEN
    F_Clamp := rMin;
ELSE
    F_Clamp := LIMIT(rMin, rValue, rMax);
END_IF
END_FUNCTION
