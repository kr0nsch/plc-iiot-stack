// Назначение: главная программа примера. Обрабатывает однократные команды HMI
//             (квитирование, сброс через интерфейс I_Resettable), вызывает FB_Example
//             и публикует состояние для HMI. Обмен с HMI — через stCmd и stSts.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/ARCHITECTURE.md, раздел «Пример в src/»
PROGRAM PRG_Main
VAR
    fbPump : FB_Example;            // насос подкачки: регулирование по уровню
    itfResettable : I_Resettable;   // сброс через интерфейс — одинаково для любых ФБ с I_Resettable
    stCmd : ST_ExampleCmd;          // команды HMI/SCADA
    stSts : ST_ExampleSts;          // состояние для HMI/SCADA
    rLevel_pct : REAL;              // уровень, % — привязать к входу модуля или задать онлайн
    xLevelValid : BOOL;             // достоверность уровня (в проекте — результат проверки NE 43)
    xPumpOn : BOOL;                 // команда на пускатель насоса — привязать к выходу модуля
END_VAR
