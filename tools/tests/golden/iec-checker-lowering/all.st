// Настройки: массив структур с константой в границе
TYPE ST_Cfg :
STRUCT
    astSlot : ST_Slot;
END_STRUCT
END_TYPE

// Слот: массив в поле структуры с начальным значением, длина строки — константа
TYPE ST_Slot :
STRUCT
    xEnable : BOOL;
    rValue : REAL;
    arStep : REAL;
    sName : STRING[32];
END_STRUCT
END_TYPE

CONFIGURATION GVL_Const
// Константы примера понижения: границы массивов и длины строк вычисляются по ним
VAR_GLOBAL CONSTANT
    SLOTS_MAX : UINT := 4;
    GRID_MAX : UINT := 7;
    NAME_LEN : UINT := 16#20;
END_VAR
END_CONFIGURATION

// Тревога: свойство с именем — ключевым словом iec_checker
INTERFACE I_Alarm
METHOD Priority__get : INT
END_METHOD
END_INTERFACE

// Назначение: пример для понижения iec-checker (tools/tests/test_assemble.py)
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/LAYOUT.md, раздел «Собранный текст build/assembled»; tools/README.md
FUNCTION F_Noop : BOOL
VAR_INPUT
    xIn : BOOL;
END_VAR

{}
END_FUNCTION

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

// Назначение: пример для понижения iec-checker (tools/tests/test_assemble.py)
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/LAYOUT.md, раздел «Собранный текст build/assembled»; tools/README.md
FUNCTION_BLOCK FB_Slots
VAR_IN_OUT CONSTANT
    stCfg : ST_Cfg;
END_VAR
VAR
    afbDelay : ARRAY[0..3] OF TON;
    aiGrid : ARRAY[0..2, 0..7] OF INT;
    aaliNested : ARRAY[0..1, 0..2] OF LINT;
    iSlot : INT;
    xAny : BOOL;
    rSum : REAL;
    wMask : WORD;
    rGain : REAL;
    iState : INT;
END_VAR
VAR CONSTANT
    GRID_LAST : INT := 2;
END_VAR
// Обращения к элементам массивов, типизированные литералы, AND_THEN и пустые ветви CASE
FOR iSlot := 0 TO GVL_Const.SLOTS_MAX - 1 DO
    afbDelay(IN := stCfg.astSlot.xEnable[iSlot], PT := T#1S, iSlot);
    xAny := xAny OR afbDelay.Q[iSlot];
    rSum := rSum + stCfg.astSlot.rValue[iSlot];
    aiGrid[CDS__IDX(iSlot, 0)] := aiGrid[CDS__IDX(0, iSlot)] + 1;
    aaliNested[CDS__IDX(0, iSlot)] := 0;
END_FOR
wMask := 16#FF;
rGain := REAL#2.0 * 1.0E3;  // lint:allow STL008 литерал с экспонентой — пример для понижения
xAny := xAny AND rSum > 0.0;
CASE iState OF
    0: CDS__NOP();
    1:
        iState := 2;
ELSE CDS__NOP();
    
END_CASE
Check(astCfg := stCfg.astSlot);
END_FUNCTION_BLOCK

FUNCTION FB_Slots__Check : BOOL
VAR_IN_OUT CONSTANT
    astCfg : ARRAY[0..3] OF ST_Slot;
END_VAR
VAR
    iIdx : INT;
END_VAR
VAR (* копии переменных FB_Slots — приближение для статанализа *)
    Check : BOOL;
END_VAR
Check := TRUE;
FOR iIdx := 0 TO GVL_Const.SLOTS_MAX - 1 DO
    Check := Check AND astCfg.rValue[iIdx] >= 0.0;
END_FOR
FB_Slots__Check := Check;
END_FUNCTION

// Назначение: пример для понижения iec-checker (tools/tests/test_assemble.py)
// Автор:      kr0nsch
// Версия:     0.1.0
// Документ:   docs/LAYOUT.md, раздел «Собранный текст build/assembled»; tools/README.md
PROGRAM PRG_Idle
VAR
    fbSlots : FB_Slots;
END_VAR
// Тело пустое: программа нужна только конфигурации задач
{}
END_PROGRAM
