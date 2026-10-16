// Нужна ли публикация: не публиковалась с подключения, контрольная, сменилось качество — сразу; изменение
// значения — не раньше tMinInterval после прошлой публикации (метрики xPeriodicOnly — только контрольно).
METHOD PRIVATE PointDue : BOOL
VAR_IN_OUT CONSTANT
    // lint:allow STL007 параметр VAR_IN_OUT CONSTANT — ссылка только для чтения, а не константа
    stPoint : ST_IiotPoint;
END_VAR
