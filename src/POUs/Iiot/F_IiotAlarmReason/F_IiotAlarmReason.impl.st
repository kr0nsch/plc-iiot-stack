IF eNew = E_IiotAlarmState.OutOfService THEN
    F_IiotAlarmReason := E_IiotAlarmReason.OosOn;
ELSIF ePrev = E_IiotAlarmState.OutOfService AND ePrev <> eNew THEN
    F_IiotAlarmReason := E_IiotAlarmReason.OosOff;
ELSIF eNew = E_IiotAlarmState.Shelved THEN
    F_IiotAlarmReason := E_IiotAlarmReason.Shelved;
ELSIF ePrev = E_IiotAlarmState.Shelved AND ePrev <> eNew THEN
    F_IiotAlarmReason := E_IiotAlarmReason.Unshelved;
ELSIF eNew = E_IiotAlarmState.SuppressedByDesign THEN
    F_IiotAlarmReason := E_IiotAlarmReason.Suppressed;
ELSIF ePrev = E_IiotAlarmState.SuppressedByDesign AND ePrev <> eNew THEN
    F_IiotAlarmReason := E_IiotAlarmReason.Unsuppressed;
ELSE
    CASE eNew OF
        E_IiotAlarmState.ActiveUnack:
            F_IiotAlarmReason := E_IiotAlarmReason.Activated;
        E_IiotAlarmState.ActiveAck:
            IF ePrev = E_IiotAlarmState.ActiveUnack OR ePrev = E_IiotAlarmState.ActiveAck THEN
                F_IiotAlarmReason := E_IiotAlarmReason.Acked;
            ELSE
                F_IiotAlarmReason := E_IiotAlarmReason.Activated;
            END_IF
        E_IiotAlarmState.RtnUnack:
            F_IiotAlarmReason := E_IiotAlarmReason.Cleared;
    ELSE
        // Normal: из RtnUnack — квитирование, иначе — условие ушло
        IF ePrev = E_IiotAlarmState.RtnUnack THEN
            F_IiotAlarmReason := E_IiotAlarmReason.Acked;
        ELSE
            F_IiotAlarmReason := E_IiotAlarmReason.Cleared;
        END_IF
    END_CASE
END_IF
