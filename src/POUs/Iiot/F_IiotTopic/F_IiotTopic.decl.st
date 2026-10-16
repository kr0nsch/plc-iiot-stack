// Назначение: полный топик <префикс>/<хвост>; пустой префикс — только хвост. Не помещается в
//             MQTT_TOPIC_LEN — пустая строка (вызывающий считает это ошибкой).
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Топики»
FUNCTION F_IiotTopic : STRING(GVL_Const.MQTT_TOPIC_LEN)
VAR_INPUT
    sPrefix : STRING(GVL_Const.IIOT_PREFIX_LEN);   // site/area/unit
    sPath : STRING(GVL_Const.MQTT_TOPIC_LEN);      // device/metric, device/alarm/suffix ...
END_VAR
