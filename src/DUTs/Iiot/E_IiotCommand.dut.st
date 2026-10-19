// Назначение: команда (поле command и последний уровень топика): имя поля ST_<Dev>Cmd устройства или
//             ST_StationCmd станции флагмана.
// Документ:   docs/plc_mqtt.md
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_IiotCommand :
(
    None := 0,   // не распознана
    SetAuto := 1,   // stCommon.xSetAuto
    SetManual := 2,   // stCommon.xSetManual
    SetOos := 3,   // stCommon.xSetOos
    Start := 4,   // xStart
    Stop := 5,   // xStop
    SpeedSp := 6,   // rSpeedSp_pct: значение 0..100 %
    ResetMaint := 7,   // xResetMaint
    SubstValue := 8,   // rSubstValue_eu / xSubstValue: значение
    Ack := 9,   // stCommon.xAck
    Reset := 10,   // stCommon.xReset
    AckReq := 11,   // stCommon.wAckReq: маска 0..65535
    ShelveReq := 12,   // stCommon.wShelveReq: маска
    UnshelveReq := 13,   // stCommon.wUnshelveReq: маска
    SetStepped := 14,   // станция: xSetStepped
    SetLevelPid := 15,   // станция: xSetLevelPid
    AckAll := 16,   // станция: xAckAll
    ResetAll := 17,   // станция: xResetAll
    Silence := 18   // станция: xSilence
) INT;
END_TYPE
