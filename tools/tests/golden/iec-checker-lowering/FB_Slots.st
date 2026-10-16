// Назначение: пример для понижения iec-checker (tools/tests/test_assemble.py)
// Автор:      <ИМЯ ФАМИЛИЯ>
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
