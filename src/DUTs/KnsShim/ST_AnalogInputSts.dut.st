// Назначение: состояние аналогового входа (44 байта, 22 регистра).
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
TYPE ST_AnalogInputSts :
STRUCT
    stCommon : ST_DeviceSts;
    rValue_eu : REAL;
    rValue_pct : REAL;
    rIn : REAL;
    eSignal : E_AiSignalState;
    uiSubstRemain_s : UINT;
END_STRUCT
END_TYPE
