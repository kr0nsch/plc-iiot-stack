// Назначение: пример для понижения iec-checker (tools/tests/test_assemble.py)
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/LAYOUT.md, раздел «Собранный текст build/assembled»; tools/README.md
FUNCTION_BLOCK FB_Alarm
VAR_INPUT
    xOn : BOOL;
END_VAR
VAR
    iPriority : INT := 1;
    tStamp : TIME;
    ltStamp : LTIME;
    tLimit : TIME := T#1H0M0S500MS;
    ltLimit : LTIME := LTIME#1H0M0S500MS;
END_VAR
// Системное время, длительности с пропуском единиц, пустые операторы и ветви
IF xOn THEN
    tStamp := CDS__TIME();
    ltStamp := CDS__LTIME();
ELSIF tStamp > T#5S THEN CDS__NOP();
    
ELSE CDS__NOP();
    // состояние не меняется
END_IF
IF tStamp >= T#1H30M THEN
    tStamp := tLimit;
END_IF;
END_FUNCTION_BLOCK

FUNCTION FB_Alarm__Priority__get : INT
VAR (* копии переменных FB_Alarm — приближение для статанализа *)
    iPriority : INT := 1;
    Priority_ : INT;
END_VAR
Priority_ := iPriority;
FB_Alarm__Priority__get := Priority_;
END_FUNCTION
