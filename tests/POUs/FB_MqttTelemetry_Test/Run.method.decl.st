// Вызов FB_MqttTelemetry: префикс vodokanal/kns1/station, ts 1792137600250, период 10 с.
METHOD PRIVATE Run
VAR_IN_OUT
    fbTelemetry : FB_MqttTelemetry;
    fbClient : FB_MqttClientFake;
    aPointTable : ARRAY[*] OF ST_IiotPoint;
END_VAR
VAR_INPUT
    ltAt : LTIME;
    xReadyIn : BOOL;
END_VAR
