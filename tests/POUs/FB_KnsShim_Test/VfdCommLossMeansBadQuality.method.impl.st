coUnit.TEST('VfdCommLossMeansBadQuality');

// Глобальные слова устройства меняются и восстанавливаются в одном вызове: другие тесты их не видят
stSaved := GVL_Devices.fbP101.stSts.stCommon;
GVL_Devices.fbP101.stSts.stCommon.eNe107 := E_Ne107Status.Good;
GVL_Devices.fbP101.stSts.stCommon.wFault := 0;
GVL_Devices.fbP101.stSts.stCommon.wWarning := 0;
fbMap.FillPoints(aPointTable := aPoints);
AssertTrue(Condition := aPoints[GVL_IiotMap.PT_P101_SPEED].eQuality = E_IiotQuality.Good, Message := 'link up: good');
GVL_Devices.fbP101.stSts.stCommon.wFault := GVL_Const.MOT_FLT_COMM;
fbMap.FillPoints(aPointTable := aPoints);
AssertTrue(Condition := aPoints[GVL_IiotMap.PT_P101_SPEED].eQuality = E_IiotQuality.Bad, Message := 'fault bit: bad');
GVL_Devices.fbP101.stSts.stCommon.wFault := 0;
GVL_Devices.fbP101.stSts.stCommon.wWarning := GVL_Const.MOT_WRN_COMM;
fbMap.FillPoints(aPointTable := aPoints);
AssertTrue(Condition := aPoints[GVL_IiotMap.PT_P101_SPEED].eQuality = E_IiotQuality.Bad,
           Message := 'warning bit: bad');
AssertTrue(Condition := aPoints[GVL_IiotMap.PT_P101_RUNNING].eQuality = E_IiotQuality.Good,
           Message := 'not a VFD link metric: good');
GVL_Devices.fbP101.stSts.stCommon := stSaved;

coUnit.TEST_FINISHED();
