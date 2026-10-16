IF rX = 1.5 THEN rX := 0.0; ELSE rX := 1.0; END_IF   // @1
aaiGrid[iSlot,
        0] := 1;
IF rX = 1.5 THEN rX := 0.0; ELSE rX := 1.0; END_IF   // @4
xQ := afbT[iSlot]
    .Q;
IF rX = 1.5 THEN rX := 0.0; ELSE rX := 1.0; END_IF   // @7
afbT[iSlot](IN := TRUE,
            PT := T#1h500ms);
IF rX = 1.5 THEN rX := 0.0; ELSE rX := 1.0; END_IF   // @10
rX := astP[iSlot]
    .rLim;
IF rX = 1.5 THEN rX := 0.0; ELSE rX := 1.0; END_IF   // @13
IF xQ THEN
    ;
ELSE
END_IF
IF rX = 1.5 THEN rX := 0.0; ELSE rX := 1.0; END_IF   // @18
tT := TIME(
);
IF rX = 1.5 THEN rX := 0.0; ELSE rX := 1.0; END_IF   // @21
CASE iSlot OF
    0:
    1: xQ := TRUE;;
ELSE
END_CASE
IF rX = 1.5 THEN rX := 0.0; ELSE rX := 1.0; END_IF   // @27
xQ := xQ AND_THEN
    (rX > 0.0);
IF rX = 1.5 THEN rX := 0.0; ELSE rX := 1.0; END_IF   // @30
aaiGrid[0]
    [iSlot] := 2;
IF rX = 1.5 THEN rX := 0.0; ELSE rX := 1.0; END_IF   // @33
afbT[iSlot
    ](IN := FALSE);
if rX = 1.5 then rX := 0.0; else rX := 1.0; end_if   // @36
IF tT = TIME() THEN xQ := TRUE; ELSE xQ := FALSE; END_IF   // @37
