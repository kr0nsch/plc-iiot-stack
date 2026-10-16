// Назначение: классификация сигнала AI (NE 43).
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_AiSignalState :
(
    Good := 0,   // норма
    UnderRange := 1,   // 3,6..3,8 мА
    OverRange := 2,   // 20,5..21,0 мА
    FailLow := 3,   // <= 3,6 мА
    FailHigh := 4,   // >= 21,0 мА
    ChannelFault := 5,   // отказ канала
    NotFinite := 6   // NaN, бесконечность
) INT;
END_TYPE
