// Назначение: пример для понижения iec-checker (tools/tests/test_assemble.py)
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/LAYOUT.md, раздел «Собранный текст build/assembled»; tools/README.md
FUNCTION_BLOCK FB_Alarm IMPLEMENTS I_Alarm
VAR_INPUT
    xOn : BOOL;
END_VAR
VAR
    iPriority : INT := 1;
    tStamp : TIME;
    ltStamp : LTIME;
    tLimit : TIME := T#1h500ms;
    ltLimit : LTIME := LTIME#1H500MS;
END_VAR
