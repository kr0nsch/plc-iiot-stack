CASE eReason OF
    E_IiotAlarmReason.Activated:
        F_IiotAlarmReasonText := 'Activated';
    E_IiotAlarmReason.Cleared:
        F_IiotAlarmReasonText := 'Cleared';
    E_IiotAlarmReason.Acked:
        F_IiotAlarmReasonText := 'Acked';
    E_IiotAlarmReason.Shelved:
        F_IiotAlarmReasonText := 'Shelved';
    E_IiotAlarmReason.Unshelved:
        F_IiotAlarmReasonText := 'Unshelved';
    E_IiotAlarmReason.ShelveExpired:
        F_IiotAlarmReasonText := 'ShelveExpired';
    E_IiotAlarmReason.Suppressed:
        F_IiotAlarmReasonText := 'Suppressed';
    E_IiotAlarmReason.Unsuppressed:
        F_IiotAlarmReasonText := 'Unsuppressed';
    E_IiotAlarmReason.OosOn:
        F_IiotAlarmReasonText := 'OosOn';
ELSE
    F_IiotAlarmReasonText := 'OosOff';
END_CASE
