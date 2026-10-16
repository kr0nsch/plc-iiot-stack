// Назначение: тревога: настройка, текущее и последнее опубликованное состояние.
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
TYPE ST_IiotAlarm :
STRUCT
    stCfg : ST_IiotAlarmCfg;
    eState : E_IiotAlarmState := E_IiotAlarmState.Normal;       // по словам устройства
    eLastState : E_IiotAlarmState := E_IiotAlarmState.Normal;   // последнее опубликованное
    xSent : BOOL;                                                // опубликовано с последнего подключения
    // Последняя публикация (ts и prev_state): после переподключения она повторяется без изменений —
    // в InfluxDB это та же точка, а не новое срабатывание. 0 — с запуска ПЛК не публиковалась.
    uliEventTs_ms : ULINT;
    eEventPrev : E_IiotAlarmState := E_IiotAlarmState.Normal;
END_STRUCT
END_TYPE
