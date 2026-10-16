// Монотонное время: время с запуска больше нуля, повторный вызов не возвращает меньшее значение.
METHOD PRIVATE NowIsMonotonic
VAR
    ltFirst : LTIME;
    ltSecond : LTIME;
END_VAR
