// Слот: массив в поле структуры с начальным значением, длина строки — константа
TYPE ST_Slot :
STRUCT
    xEnable : BOOL;
    rValue : REAL;
    arStep : ARRAY[1..4] OF REAL := [0.5, 1.0, 1.5, 2.0];
    sName : STRING(GVL_Const.NAME_LEN);
END_STRUCT
END_TYPE
