// Назначение: статус NAMUR NE 107 устройства.
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_Ne107Status :
(
    Good := 0,   // норма
    MaintenanceRequired := 1,   // M
    OutOfSpecification := 2,   // S
    CheckFunction := 3,   // C
    Failure := 4   // F
) INT;
END_TYPE
