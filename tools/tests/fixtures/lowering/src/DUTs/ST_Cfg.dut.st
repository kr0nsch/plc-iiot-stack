// Настройки: массив структур с константой в границе
TYPE ST_Cfg :
STRUCT
    astSlot : ARRAY[0..GVL_Const.SLOTS_MAX - 1] OF ST_Slot;
END_STRUCT
END_TYPE
