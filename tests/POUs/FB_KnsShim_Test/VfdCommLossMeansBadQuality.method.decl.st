// Потеря связи с ПЧ — quality bad у метрик ПЧ: и как отказ (wFault), и как предупреждение (wWarning).
METHOD PRIVATE VfdCommLossMeansBadQuality
VAR_INST
    fbMap : FB_IiotKnsMap;
    aPoints : ARRAY[1..GVL_IiotMap.POINT_COUNT] OF ST_IiotPoint;
END_VAR
VAR
    stSaved : ST_DeviceSts;     // слова P101 до теста — восстанавливаются в конце
END_VAR
