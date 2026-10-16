// Назначение: команды HMI/SCADA для примера FB_Example (насос подкачки).
//             Однократные команды (xAck, xReset) сбрасывает ПЛК после выполнения.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/ARCHITECTURE.md, раздел «Пример в src/»
TYPE ST_ExampleCmd :
STRUCT
    // требуемый режим; после холодного старта устройство выведено из работы
    eMode : E_DeviceMode := E_DeviceMode.OutOfService;
    // уставка отключения, % диапазона датчика
    rSetpoint_pct : REAL := GVL_Const.EXAMPLE_SP_DEFAULT_PCT;
    xManualOn : BOOL;       // ручная команда «включить» (режим Manual)
    xAck : BOOL;            // квитирование отказа (однократная команда)
    xReset : BOOL;          // сброс состояния и счётчика (однократная команда)
END_STRUCT
END_TYPE
