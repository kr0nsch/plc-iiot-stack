CASE eQosIn OF
    E_MqttQos.AtLeastOnce:
        ToLibQos := SD_MQTT.QoS.AtLeastOnce;
    E_MqttQos.ExactlyOnce:
        ToLibQos := SD_MQTT.QoS.ExactlyOnce;
ELSE
    ToLibQos := SD_MQTT.QoS.AtMostOnce;
END_CASE
