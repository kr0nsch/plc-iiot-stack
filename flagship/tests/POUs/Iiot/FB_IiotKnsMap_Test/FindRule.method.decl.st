// Строка белого списка GVL_IiotMap.RULE_CFG для устройства и команды; нет такой — 0.
METHOD PRIVATE FindRule : DINT
VAR_INPUT
    sDevice : STRING(GVL_Const.IIOT_DEVICE_LEN);
    eCommand : E_IiotCommand;
END_VAR
VAR
    diIdx : DINT;
END_VAR
