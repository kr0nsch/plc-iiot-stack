// Назначение: пример для понижения iec-checker (tools/tests/test_assemble.py)
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/LAYOUT.md, раздел «Собранный текст build/assembled»; tools/README.md
FUNCTION_BLOCK FB_Slots
VAR_IN_OUT CONSTANT
    stCfg : ST_Cfg;
END_VAR
VAR
    afbDelay : ARRAY[0..GVL_Const.SLOTS_MAX - 1] OF TON;
    aiGrid : ARRAY[0..GRID_LAST, 0..GVL_Const.GRID_MAX] OF INT;
    aaliNested : ARRAY[0..1] OF ARRAY[0..2] OF LINT;
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
