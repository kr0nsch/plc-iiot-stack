// Назначение: состояние двигателя.
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_MotorState :
(
    Stopped := 0,   // стоп
    Starting := 1,   // пуск
    Running := 2,   // работа
    Stopping := 3,   // останов
    Fault := 4   // отказ
) INT;
END_TYPE
