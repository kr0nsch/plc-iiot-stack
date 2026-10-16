// Назначение: общий заголовок команд устройства.
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
TYPE ST_DeviceCmd :
STRUCT
    xSetAuto : BOOL;       // импульс: в Auto
    xSetManual : BOOL;     // импульс: в Manual
    xSetOos : BOOL;        // импульс: вывести из работы
    xReset : BOOL;         // импульс: сброс отказов и квитирование
    xAck : BOOL;           // импульс: квитировать тревоги
    wAckReq : WORD;        // маска: квитировать слоты
    wShelveReq : WORD;     // маска: отложить слоты
    wUnshelveReq : WORD;   // маска: вернуть слоты
END_STRUCT
END_TYPE
