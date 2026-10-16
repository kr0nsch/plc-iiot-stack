// Назначение: состояние двигателя (68 байт, 34 регистра).
// Заглушка флагмана: копия типа plc-process-lib (docs API.md, 4.1-4.6, 11.1, 12.1, 13.1) для сборки без
// библиотеки. При встраивании во флагман удаляется вместе с папкой KnsShim.
{attribute 'qualified_only'}
TYPE ST_MotorSts :
STRUCT
    stCommon : ST_DeviceSts;
    eState : E_MotorState;
    wInterlock : WORD;
    wPermitMissing : WORD;
    uiFirstOut : UINT;
    uiInhibitRemain_s : UINT;
    uiStartsLastHour : UINT;
    rRunTime_h : REAL;
    udiStarts : UDINT;
    rRunTimeMaint_h : REAL;
    udiStartsMaint : UDINT;
    rSpeedRef_pct : REAL;
    rSpeedAct_pct : REAL;
    udiRunCurrent_s : UDINT;
END_STRUCT
END_TYPE
