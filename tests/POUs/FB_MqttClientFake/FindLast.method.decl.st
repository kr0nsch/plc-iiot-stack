// Для тестов: индекс последнего сообщения с топиком sTopic; нет — 0.
METHOD FindLast : UINT
VAR_INPUT
    sTopic : STRING(GVL_Const.MQTT_TOPIC_LEN);
END_VAR
VAR
    diIdx : DINT;
END_VAR
