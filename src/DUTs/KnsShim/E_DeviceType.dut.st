// Назначение: тип устройства в stSts.stCommon.eDevType.
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_DeviceType :
(
    None := 0,   // до первого вызова
    AnalogInput := 1,   // AI
    DigitalInput := 2,   // DI
    Motor := 3,   // двигатель
    MotorVfd := 4,   // двигатель с ПЧ
    Valve := 5,   // задвижка
    ControlValve := 6,   // регулирующий клапан
    Pid := 7   // ПИД
) INT;
END_TYPE
