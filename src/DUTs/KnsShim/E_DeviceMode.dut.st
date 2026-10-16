// Назначение: режим устройства.
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_DeviceMode :
(
    Auto := 1,   // автомат
    Manual := 2,   // ручной дистанционный
    Local := 3,   // местный
    OutOfService := 4   // выведено из работы
) INT;
END_TYPE
