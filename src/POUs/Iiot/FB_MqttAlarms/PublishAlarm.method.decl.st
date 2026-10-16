// Опубликовать тревогу. TRUE — обработана (опубликована или пропущена). Что публикуется:
// - событие: состояние изменилось с прошлой публикации (в том числе пока связи не было) — ts сейчас;
// - повтор после переподключения: состояние не менялось — последняя публикация с её ts и prev_state
//   (в InfluxDB та же точка: активная тревога не считается новым срабатыванием);
// - снимок: с запуска ПЛК тревога не публиковалась — prev_state = state, ts сейчас.
METHOD PRIVATE PublishAlarm : BOOL
VAR_IN_OUT
    stAlarm : ST_IiotAlarm;
END_VAR
VAR
    ePrev : E_IiotAlarmState;
    uliTs : ULINT;
    xEvent : BOOL;
    sCode : STRING(GVL_Const.IIOT_TEXT_LEN);
    sPriority : STRING(GVL_Const.IIOT_TEXT_LEN);
    sPath : STRING(GVL_Const.MQTT_TOPIC_LEN);
END_VAR
