// Назначение: результат последней команды устройства.
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_CmdResult :
(
    None := 0,   // команд не было
    Accepted := 1,   // принята
    RejectedMode := 2,   // не в этом режиме
    RejectedInterlock := 3,   // блокировка
    RejectedPermit := 4,   // нет разрешения
    RejectedInhibit := 5,   // запрет пуска
    RejectedFault := 6,   // отказ
    RejectedState := 7,   // не в этом состоянии
    RejectedNotSupported := 8,   // не поддерживается
    RejectedCfg := 9,   // нет корректной Cfg
    SubstExpired := 10   // подмена снята по времени
) INT;
END_TYPE
