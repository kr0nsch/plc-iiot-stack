// Назначение: уровень качества обслуживания MQTT (QoS).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_MqttQos :
(
    AtMostOnce := 0,   // QoS 0: не более одного раза
    AtLeastOnce := 1,   // QoS 1: не менее одного раза (возможны повторы)
    ExactlyOnce := 2   // QoS 2: ровно один раз
) INT;
END_TYPE
