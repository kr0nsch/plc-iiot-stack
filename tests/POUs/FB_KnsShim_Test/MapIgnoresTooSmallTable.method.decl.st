// FB_IiotKnsMap: массив меньше перечня метрик или слов тревог не заполняется (нет выхода за границы).
METHOD PRIVATE MapIgnoresTooSmallTable
VAR
    fbMap : FB_IiotKnsMap;
    aSmallPoints : ARRAY[1..2] OF ST_IiotPoint;
    aSmallWords : ARRAY[1..2] OF ST_IiotAlarmWords;
    aShiftedPoints : ARRAY[2..GVL_IiotMap.POINT_COUNT] OF ST_IiotPoint;    // верхняя граница достаточна, нижняя — нет
END_VAR
