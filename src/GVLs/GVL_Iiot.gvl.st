// Назначение: настройки и состояние ПЛК-части IIoT-стека для HMI и SCADA (OPC UA). Настройки задаёт
//             наладчик в IDE; по OPC UA они только читаются, пароль брокера в символы не выгружается
//             (атрибут в ST_MqttBrokerCfg).
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Настройки и состояние»
{attribute 'qualified_only'}
VAR_GLOBAL
    {attribute 'symbol' := 'read'}
    stIiotCfg : ST_IiotCfg;   // настройки: брокер, топики, приём команд; по OPC UA — только чтение
    {attribute 'symbol' := 'read'}
    stIiotSts : ST_IiotSts;   // состояние связи и счётчики
END_VAR
