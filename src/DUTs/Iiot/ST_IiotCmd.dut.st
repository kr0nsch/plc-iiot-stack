// Назначение: команда, прошедшая проверки шлюза (FB_MqttCommands.stCmd).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_IiotCmd :
STRUCT
    diRule : DINT;                                  // строка белого списка
    sDevice : STRING(GVL_Const.IIOT_DEVICE_LEN);
    sCommand : STRING(GVL_Const.IIOT_LEVEL_LEN);    // последний уровень топика
    eCommand : E_IiotCommand := E_IiotCommand.None;
    rValue : REAL;                                  // для команд-значений и масок
    sCmdId : STRING(GVL_Const.CMD_ID_LEN);
END_STRUCT
END_TYPE
