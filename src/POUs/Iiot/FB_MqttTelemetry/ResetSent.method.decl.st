// Связи нет: сбросить признаки «опубликовано», чтобы после рождения опубликовать всё; период — заново.
METHOD PRIVATE ResetSent
VAR_IN_OUT
    aPointTable : ARRAY[*] OF ST_IiotPoint;
END_VAR
VAR
    diIdx : DINT;
END_VAR
