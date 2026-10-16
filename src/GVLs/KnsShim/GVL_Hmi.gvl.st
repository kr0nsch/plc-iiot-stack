// Назначение: заглушка GVL_Hmi флагмана: структуры команд st<TAG>Cmd с теми же именами и типами (без пространства PL).
//             Источник имён: iolistgen 0.1.0, перечень КНС-1 (SHA-256 06336d13c4b2), проект 02.
//             При встраивании во флагман заменяется сгенерированным файлом с типами PL.*.
// Автор:      <ИМЯ ФАМИЛИЯ>
// Версия:     0.1.0
// Документ:   docs/plc_mqtt.md, раздел «Заглушка флагмана»
{attribute 'qualified_only'}
VAR_GLOBAL
    xApplyProjectCfg : BOOL;  // импульс: применить уставки проекта (PRG_ApplyProjectCfg); сбрасывает PRG_Devices
    stP101Cmd : ST_MotorCmd;  // 11 · Насос Н1
    stP102Cmd : ST_MotorCmd;  // 12 · Насос Н2
    stP103Cmd : ST_MotorCmd;  // 13 · Насос Н3
    stV1Cmd : ST_MotorCmd;  // 14 · Вытяжной вентилятор В1 павильона
    stLT101Cmd : ST_AnalogInputCmd;  // 101 · Уровень в приёмном резервуаре
    stLS102Cmd : ST_DigitalInputCmd;  // 102 · Поплавок «аварийно высокий уровень» (H, 4,2 м)
    stLS103Cmd : ST_DigitalInputCmd;  // 103 · Поплавок «сухой ход» (L, 0,4 м)
    stIT111Cmd : ST_AnalogInputCmd;  // 111 · Насос Н1: ток двигателя (измеряет ПЧ)
    stTS112Cmd : ST_DigitalInputCmd;  // 112 · Насос Н1: перегрев обмотки (термовыключатели, реле защиты насоса)
    // 113 · Насос Н1: протечка в камеру статора (датчик влажности, реле защиты насоса)
    stMS113Cmd : ST_DigitalInputCmd;
    stIT121Cmd : ST_AnalogInputCmd;  // 121 · Насос Н2: ток двигателя (измеряет ПЧ)
    stTS122Cmd : ST_DigitalInputCmd;  // 122 · Насос Н2: перегрев обмотки (термовыключатели, реле защиты насоса)
    // 123 · Насос Н2: протечка в камеру статора (датчик влажности, реле защиты насоса)
    stMS123Cmd : ST_DigitalInputCmd;
    stIT131Cmd : ST_AnalogInputCmd;  // 131 · Насос Н3: ток двигателя (измеряет ПЧ)
    stTS132Cmd : ST_DigitalInputCmd;  // 132 · Насос Н3: перегрев обмотки (термовыключатели, реле защиты насоса)
    // 133 · Насос Н3: протечка в камеру статора (датчик влажности, реле защиты насоса)
    stMS133Cmd : ST_DigitalInputCmd;
    stPT201Cmd : ST_AnalogInputCmd;  // 201 · Давление в напорном коллекторе
    stFT202Cmd : ST_AnalogInputCmd;  // 202 · Расход в напорном коллекторе
    stLS203Cmd : ST_DigitalInputCmd;  // 203 · Затопление камеры задвижек
    stES301Cmd : ST_DigitalInputCmd;  // 301 · Напряжение на вводе в норме (реле контроля фаз)
    stYS302Cmd : ST_DigitalInputCmd;  // 302 · ИБП шкафа управления: работа от батарей
    stYS303Cmd : ST_DigitalInputCmd;  // 303 · ИБП шкафа управления: неисправность или разряд батарей
    stAT401Cmd : ST_AnalogInputCmd;  // 401 · Концентрация сероводорода H₂S в павильоне
    stAT402Cmd : ST_AnalogInputCmd;  // 402 · Концентрация метана CH₄ в павильоне
    stTT403Cmd : ST_AnalogInputCmd;  // 403 · Температура воздуха в павильоне
    stZS404Cmd : ST_DigitalInputCmd;  // 404 · Дверь павильона открыта
    stYS405Cmd : ST_DigitalInputCmd;  // 405 · Пожар (сигнал прибора пожарной сигнализации)
    stHS501Cmd : ST_DigitalInputCmd;  // 501 · Кнопка «Сброс аварий» на двери шкафа управления
    stHS502Cmd : ST_DigitalInputCmd;  // 502 · Кнопка «Отключить звук» на двери шкафа управления
END_VAR
