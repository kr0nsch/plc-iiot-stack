CASE eState OF
    E_IiotAlarmState.Normal:
        F_IiotAlarmStateText := 'Normal';
    E_IiotAlarmState.ActiveUnack:
        F_IiotAlarmStateText := 'ActiveUnack';
    E_IiotAlarmState.ActiveAck:
        F_IiotAlarmStateText := 'ActiveAck';
    E_IiotAlarmState.RtnUnack:
        F_IiotAlarmStateText := 'RtnUnack';
    E_IiotAlarmState.Shelved:
        F_IiotAlarmStateText := 'Shelved';
    E_IiotAlarmState.SuppressedByDesign:
        F_IiotAlarmStateText := 'SuppressedByDesign';
ELSE
    F_IiotAlarmStateText := 'OutOfService';
END_CASE
