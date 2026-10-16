// Назначение: приоритет тревоги.
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_AlarmPriority :
(
    None := 0,   // выключена
    Low := 1,   // низкий
    Medium := 2,   // средний
    High := 3,   // высокий
    Critical := 4   // резерв
) INT;
END_TYPE
