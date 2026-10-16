// Индекс поля с ключом sKey (с учётом регистра); нет — 0.
METHOD FindField : UINT
VAR_INPUT
    sKey : STRING(GVL_Const.JSON_KEY_LEN);
END_VAR
VAR
    uiIdx : UINT;
END_VAR
