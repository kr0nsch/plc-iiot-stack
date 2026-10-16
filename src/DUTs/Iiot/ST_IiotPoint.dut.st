// Назначение: метрика телеметрии: настройка, текущее и последнее опубликованное значение.
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_IiotPoint :
STRUCT
    stCfg : ST_IiotPointCfg;
    // текущее (заполняет FB_IiotKnsMap.FillPoints или PRG_Iiot)
    lrValue : LREAL;
    eQuality : E_IiotQuality := E_IiotQuality.Bad;
    // последнее опубликованное (FB_MqttTelemetry)
    lrLastValue : LREAL;
    lrLastFinite : LREAL;                           // последнее опубликованное конечное значение
    eLastQuality : E_IiotQuality := E_IiotQuality.Bad;
    ltLastSent : LTIME;
    xSent : BOOL;                                   // опубликовано с последнего подключения
    xForce : BOOL;                                  // опубликовать независимо от изменения (период)
END_STRUCT
END_TYPE
