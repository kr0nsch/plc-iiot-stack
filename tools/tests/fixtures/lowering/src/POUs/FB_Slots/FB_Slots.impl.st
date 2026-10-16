// Обращения к элементам массивов, типизированные литералы, AND_THEN и пустые ветви CASE
FOR iSlot := 0 TO GVL_Const.SLOTS_MAX - 1 DO
    afbDelay[iSlot](IN := stCfg.astSlot[iSlot].xEnable, PT := T#1S);
    xAny := xAny OR afbDelay[iSlot].Q;
    rSum := rSum + stCfg.astSlot[iSlot].rValue;
    aiGrid[iSlot, 0] := aiGrid[0, iSlot] + 1;
    aaliNested[0][iSlot] := 0;
END_FOR
wMask := WORD#16#FF;
rGain := REAL#2 * 1E3;  // lint:allow STL008 литерал с экспонентой — пример для понижения
xAny := xAny AND_THEN rSum > 0.0;
CASE iState OF
    0:
    1:
        iState := 2;
ELSE
    ;
END_CASE
Check(astCfg := stCfg.astSlot);
