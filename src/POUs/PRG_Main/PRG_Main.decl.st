// Назначение: служебная программа рабочей сборки этого репозитория (cds.py build, режим normal): ядро
//             шлюза MQTT собирается как библиотека, а программа обмена PRG_Iiot с привязкой к переменным
//             КНС-1 работает во флагмане (flagship/, docs/plc_mqtt.md). CODESYS 3.5.17 не собирает
//             приложение без задач, поэтому задаче MainTask нужна программа. Единственное действие —
//             признак «часы ПЛК установлены» в GVL_Iiot.stIiotSts.xClockValid для проверки онлайн: без
//             часов шлюз обмен не начинает (решение F9, docs/ASSUMPTIONS.md). Проверку всех объектов
//             ядра даёт тестовая сборка (cds.py build --tests, cds.py test). В .library программа не входит.
// Автор:      kr0nsch
// Версия:     0.2.0
// Документ:   docs/plc_mqtt.md, раздел «Состав»
PROGRAM PRG_Main
VAR
    uliTs_ms : ULINT;                     // календарное время ПЛК, мс UTC
END_VAR
VAR CONSTANT
    RTC_OK : UDINT := 0;                  // SysTimeRtcHighResGet: «нет ошибки» (ERR_OK)
END_VAR
