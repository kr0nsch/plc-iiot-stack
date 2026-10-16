// Многострочные начальное значение массива и вложенный массив в полях структуры
TYPE ST_Probe :
STRUCT
    arStep : ARRAY[1..4] OF REAL := [0.5, 1.0,
        1.5, 2.0];
    aaiGrid : ARRAY[0..1] OF
        ARRAY[0..2] OF INT;
    sName : STRING(GVL_Const.NAME_SIZE) := 'abc';   // @8
    rLim : REAL := 1.0;                               // @9
END_STRUCT
END_TYPE
