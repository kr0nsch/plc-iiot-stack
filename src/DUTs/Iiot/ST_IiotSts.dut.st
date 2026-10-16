// Назначение: состояние ПЛК-части IIoT-стека для HMI и SCADA (GVL_Iiot.stIiotSts).
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_IiotSts :
STRUCT
    eConnState : E_MqttConnState := E_MqttConnState.Disabled;
    eNe107 : E_IiotNe107 := E_IiotNe107.CheckFunction;
    udiConnects : UDINT;
    udiDisconnects : UDINT;
    udiConnectFailures : UDINT;
    diLastError : DINT;
    udiPublished : UDINT;                     // телеметрия и тревоги, принятые клиентом
    udiPublishFailed : UDINT;                 // клиент не принял (повторится)
    uiQueue : UINT;                           // записей ждут публикации
    udiDropped : UDINT;                       // сообщений отброшено (не поместились, ответ не принят)
    udiCmdAccepted : UDINT;
    udiCmdRejected : UDINT;                   // отказы с ответом и без ответа
    eLastCmdReason : E_IiotCmdReason := E_IiotCmdReason.Ok;
    xClockValid : BOOL;                       // часы ПЛК в диапазоне схемы: обмен разрешён
END_STRUCT
END_TYPE
